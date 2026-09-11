import importlib.util
import inspect
import sys
from typing import Dict, Type

from pydantic import BaseModel

from domains.management.models.base import AppBaseModel
from shared.resource_manager import ResourceManager


class ModelRegistry:
    """Реестр pydantic моделей, обнаруживаемых в модулях по указанному пути.
    Далее может использоваться для регистрации фабрик, в т.ч. repository factory"""

    def __init__(self):
        self.models: Dict[str, Type[BaseModel]] = {}
        # self.discover_models(models_module) - TODO перейти на discover_models
        register_models = [
           # Добавлять здесь
        ]
        for model in register_models:
            self.models[model.model_fields["type"].default] = model

    def discover_models(self, module) -> None:
        """
        Discover all Pydantic models in the specified package path
        """
        package_dir = ResourceManager.get_module_path(module)

        for py_file in package_dir.glob("**/*.py"):
            if py_file.name == "__init__.py":
                continue

            # Convert file path to module path
            relative_path = py_file.relative_to(package_dir.parent)
            module_name = ".".join(relative_path.with_suffix("").parts)

            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec is None:
                    raise ValueError(f"Cannot import file {py_file} from module {module_name}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                if spec.loader is None:
                    raise ValueError(f"Cannot find loader for file/module {py_file}/{module_name}")
                spec.loader.exec_module(module)
                for _, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, AppBaseModel)
                        and obj.__module__ == module_name
                        and "type" in obj.model_fields
                        and obj not in self.models.values()
                    ):
                        self.models[obj.model_fields["type"].default] = obj
            except Exception as e:
                print(f"Error loading models from {py_file}: {e}")
                continue
