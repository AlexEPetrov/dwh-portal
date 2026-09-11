from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import importlib.resources
else:
    import importlib_resources


class ResourceManager:
    """Менеджер ресурсов проекта. Доступ к файлам дерева проекта в ран-тайм"""
    
    @staticmethod    
    def get_resource_path(module, resource_file_path: str) -> str:
        """Возвращает полный путь по относительному пути ресурса"""
        if sys.version_info >= (3, 11):
            path = importlib.resources.files(module).joinpath(resource_file_path)
        else:
            path = importlib_resources.files(module).joinpath(resource_file_path)            

        return path
    
    @staticmethod    
    def get_resource_string(module, resource_file_path: str) -> str:
        """Возвращает содержание файла ресурса (UTF-8)"""
        path = ResourceManager.get_resource_path(module, resource_file_path)         
        with open(path, encoding="UTF-8") as file:
            return file.read() 
        
    @staticmethod    
    def get_module_path(module) -> Path:
        """Возвращает путь модуля проекта"""
        if sys.version_info >= (3, 11):
            path = importlib.resources.files(module)
        else:
            path = importlib_resources.files(module)
        return Path(path)    