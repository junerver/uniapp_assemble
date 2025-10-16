"""
文件服务。

处理文件上传、存储和验证功能。
"""

import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import uuid4

from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class FileService:
    """文件服务类，处理文件上传和管理。"""

    def __init__(self):
        """初始化文件服务。"""
        self.upload_dir = Path(settings.upload_directory)
        self.ensure_upload_directory()

    def ensure_upload_directory(self) -> None:
        """确保上传目录存在。"""
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"上传目录已准备: {self.upload_dir}")
        except Exception as e:
            logger.error(f"创建上传目录失败: {e}")
            raise

    async def save_uploaded_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str
    ) -> Dict[str, Any]:
        """
        保存上传的文件。

        Args:
            file_content: 文件内容
            filename: 原始文件名
            content_type: 文件MIME类型

        Returns:
            包含文件信息的字典

        Raises:
            ValueError: 文件验证失败
            OSError: 文件保存失败
        """
        try:
            # 验证文件
            await self._validate_file(file_content, filename, content_type)

            # 生成唯一文件名
            file_id = str(uuid4())
            file_extension = Path(filename).suffix
            safe_filename = f"{file_id}{file_extension}"
            file_path = self.upload_dir / safe_filename

            # 保存文件
            with open(file_path, "wb") as f:
                f.write(file_content)

            # 获取文件信息
            file_size = len(file_content)
            file_info = {
                "file_id": file_id,
                "original_filename": filename,
                "safe_filename": safe_filename,
                "file_path": str(file_path),
                "file_size": file_size,
                "content_type": content_type,
                "is_archive": self._is_archive_file(filename, content_type),
                "status": "uploaded"
            }

            logger.info(f"文件保存成功: {filename} -> {safe_filename}")
            return file_info

        except Exception as e:
            logger.error(f"保存文件失败 {filename}: {e}")
            raise

    async def _validate_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str
    ) -> None:
        """
        验证上传的文件。

        Args:
            file_content: 文件内容
            filename: 文件名
            content_type: MIME类型

        Raises:
            ValueError: 文件验证失败
        """
        # 检查文件大小
        max_file_size = settings.max_file_size  # 从配置获取
        if len(file_content) > max_file_size:
            raise ValueError(f"文件大小超过限制: {len(file_content)} > {max_file_size}")

        # 检查文件名
        if not filename or filename.strip() == "":
            raise ValueError("文件名不能为空")

        # 检查文件扩展名
        allowed_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz'}
        file_extension = Path(filename).suffix.lower()
        if file_extension not in allowed_extensions:
            raise ValueError(f"不支持的文件类型: {file_extension}")

        # 检查MIME类型（允许通用的 octet-stream，主要依赖文件扩展名验证）
        allowed_mime_types = {
            'application/zip',
            'application/x-rar-compressed',
            'application/x-compressed',  # Windows对RAR文件的MIME类型识别
            'application/x-7z-compressed',
            'application/x-tar',
            'application/gzip',
            'application/octet-stream',  # 允许通用二进制类型
            'application/x-zip-compressed',  # Windows常见的ZIP MIME类型
            'application/x-rar',  # 某些系统对RAR文件的MIME类型识别
            'application/x-msdownload',  # Windows对某些压缩文件的识别
            'application/x-msdos-program'  # 另一个Windows常见的MIME类型
        }
        if content_type not in allowed_mime_types:
            raise ValueError(f"不支持的MIME类型: {content_type}")

    def _is_archive_file(self, filename: str, content_type: str) -> bool:
        """判断是否为压缩文件。"""
        archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz'}
        archive_mime_types = {
            'application/zip',
            'application/x-rar-compressed',
            'application/x-compressed',  # Windows对RAR文件的MIME类型识别
            'application/x-7z-compressed',
            'application/x-tar',
            'application/gzip',
            'application/x-rar',  # 某些系统对RAR文件的MIME类型识别
            'application/x-msdownload',  # Windows对某些压缩文件的识别
            'application/x-msdos-program'  # 另一个Windows常见的MIME类型
        }

        file_extension = Path(filename).suffix.lower()
        return (file_extension in archive_extensions or
                content_type in archive_mime_types)

    async def extract_archive(self, file_path: str, extract_to: Optional[str] = None) -> Dict[str, Any]:
        """
        解压压缩文件。

        Args:
            file_path: 压缩文件路径
            extract_to: 解压目标目录，如果为None则使用默认目录

        Returns:
            解压结果信息

        Raises:
            ValueError: 文件不是有效的压缩文件
            OSError: 解压失败
        """
        try:
            source_path = Path(file_path)
            if not source_path.exists():
                raise ValueError(f"文件不存在: {file_path}")

            # 确定解压目录
            if extract_to:
                extract_dir = Path(extract_to)
            else:
                extract_dir = self.upload_dir / f"extracted_{source_path.stem}"

            extract_dir.mkdir(parents=True, exist_ok=True)

            # 根据文件类型解压
            extracted_files = []
            if source_path.suffix.lower() == '.zip':
                extracted_files = await self._extract_zip(source_path, extract_dir)
            else:
                # TODO: 支持其他压缩格式
                raise ValueError(f"暂不支持的压缩格式: {source_path.suffix}")

            result = {
                "extracted": True,
                "extract_dir": str(extract_dir),
                "file_count": len(extracted_files),
                "extracted_files": extracted_files,
                "status": "completed"
            }

            logger.info(f"文件解压成功: {file_path} -> {extract_dir}, {len(extracted_files)} 个文件")
            return result

        except Exception as e:
            logger.error(f"解压文件失败 {file_path}: {e}")
            raise

    async def _extract_zip(self, zip_path: Path, extract_dir: Path) -> List[str]:
        """解压ZIP文件。"""
        extracted_files = []

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 获取文件列表
                file_list = zip_ref.namelist()

                # 解压所有文件
                zip_ref.extractall(extract_dir)

                # 记录解压的文件
                for file_name in file_list:
                    extracted_path = extract_dir / file_name
                    if extracted_path.exists():
                        extracted_files.append({
                            "name": file_name,
                            "path": str(extracted_path),
                            "size": extracted_path.stat().st_size if extracted_path.is_file() else 0,
                            "is_file": extracted_path.is_file(),
                            "is_directory": extracted_path.is_dir()
                        })

        except zipfile.BadZipFile:
            raise ValueError("无效的ZIP文件")

        return extracted_files

    async def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文件信息。

        Args:
            file_id: 文件ID

        Returns:
            文件信息字典，如果文件不存在返回None
        """
        try:
            # 通过文件ID查找文件（这里简化实现，实际可能需要数据库）
            for file_path in self.upload_dir.glob(f"{file_id}*"):
                if file_path.is_file():
                    stat = file_path.stat()
                    return {
                        "file_id": file_id,
                        "file_path": str(file_path),
                        "file_name": file_path.name,
                        "file_size": stat.st_size,
                        "created_time": stat.st_ctime,
                        "modified_time": stat.st_mtime,
                        "is_file": True
                    }
            return None

        except Exception as e:
            logger.error(f"获取文件信息失败 {file_id}: {e}")
            return None

    async def delete_file(self, file_id: str) -> bool:
        """
        删除文件。

        Args:
            file_id: 文件ID

        Returns:
            删除是否成功
        """
        try:
            # 查找并删除文件
            for file_path in self.upload_dir.glob(f"{file_id}*"):
                if file_path.is_file():
                    file_path.unlink()
                    logger.info(f"文件删除成功: {file_path}")
                    return True
            return False

        except Exception as e:
            logger.error(f"删除文件失败 {file_id}: {e}")
            return False

    async def cleanup_expired_files(self, max_age_hours: int = 24) -> int:
        """
        清理过期文件。

        Args:
            max_age_hours: 最大保留时间（小时）

        Returns:
            清理的文件数量
        """
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            cleaned_count = 0

            for file_path in self.upload_dir.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.info(f"清理过期文件: {file_path}")

            logger.info(f"清理完成，删除 {cleaned_count} 个过期文件")
            return cleaned_count

        except Exception as e:
            logger.error(f"清理过期文件失败: {e}")
            return 0

    def get_upload_directory_info(self) -> Dict[str, Any]:
        """
        获取上传目录信息。

        Returns:
            目录信息字典
        """
        try:
            total_files = 0
            total_size = 0
            file_types = {}

            for file_path in self.upload_dir.iterdir():
                if file_path.is_file():
                    total_files += 1
                    size = file_path.stat().st_size
                    total_size += size

                    # 统计文件类型
                    extension = file_path.suffix.lower()
                    file_types[extension] = file_types.get(extension, 0) + 1

            return {
                "upload_directory": str(self.upload_dir),
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": file_types,
                "directory_exists": self.upload_dir.exists()
            }

        except Exception as e:
            logger.error(f"获取上传目录信息失败: {e}")
            return {
                "upload_directory": str(self.upload_dir),
                "total_files": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "file_types": {},
                "directory_exists": False,
                "error": str(e)
            }