# scripts/generate_jsonschemas.py
import json
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Type, Dict, List, Optional
from pydantic import BaseModel


def find_project_root(start_path: Path) -> Path:
    """
    Находит корневую директорию проекта (где находится src/ или pyproject.toml)
    """
    for parent in [start_path] + list(start_path.parents):
        if (parent / "src").exists() or (parent / "pyproject.toml").exists():
            return parent
    return start_path


def discover_models_in_directory(
    directory_path: Path,
    project_root: Optional[Path] = None
) -> Dict[str, Type[BaseModel]]:
    """
    Обнаруживает все Pydantic модели в Python файлах указанной директории.
    """
    models = {}
    directory_path = Path(directory_path)
    
    if not directory_path.exists():
        print(f"❌ Директория {directory_path} не существует")
        return models
    
    # Находим корень проекта и добавляем его в sys.path
    if project_root is None:
        project_root = find_project_root(directory_path)
    
    # Добавляем корневую директорию (где находится src)
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        print(f"📁 Добавлен в sys.path: {project_root}")
    
    # Также добавляем src директорию если она есть
    src_dir = project_root / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
        print(f"📁 Добавлен в sys.path: {src_dir}")
    
    # Обходим все .py файлы
    for py_file in directory_path.rglob("*.py"):
        if py_file.name == "__init__.py" or py_file.name.startswith("test_"):
            continue
        
        # Формируем имя модуля относительно project_root
        try:
            rel_path = py_file.relative_to(project_root)
            module_name = str(rel_path.with_suffix('')).replace('/', '.')
            # Убираем 'src.' если есть
            module_name = module_name.replace('src.', '', 1)
        except ValueError:
            # Если файл вне project_root, используем абсолютный путь
            module_name = str(py_file.with_suffix('')).replace('/', '.')
        
        try:
            print(f"  🔄 Импорт {module_name} из {py_file}")
            
            # Импортируем модуль
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Ищем классы BaseModel
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, BaseModel) 
                        and obj != BaseModel 
                        and obj.__module__ == module.__name__):
                        models[f"{module_name}.{name}"] = obj
                        print(f"    ✅ Найдена модель: {name}")
                        
        except Exception as e:
            print(f"  ⚠️ Ошибка импорта {py_file.name}: {e}")
            continue
    
    return models


def generate_json_schemas(
    models_path: str | Path,
    output_dir: str | Path,
    project_root: Optional[str | Path] = None,
    by_alias: bool = True,
    indent: int = 2,
    verbose: bool = True
) -> None:
    """
    Генерирует JSON Schema для всех Pydantic моделей.
    """
    models_path = Path(models_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Находим корень проекта
    if project_root:
        project_root = Path(project_root)
    else:
        project_root = find_project_root(models_path)
    
    print(f"🔍 Поиск моделей в {models_path}...")
    print(f"📁 Корень проекта: {project_root}")
    
    models = discover_models_in_directory(models_path, project_root)
    
    if not models:
        print("\n⚠️ Модели не найдены. Возможные причины:")
        print("  1. Неправильный путь к моделям")
        print("  2. Отсутствуют файлы __init__.py в пакетах")
        print("  3. Ошибки импорта зависимостей моделей")
        return
    
    print(f"\n✅ Найдено {len(models)} моделей\n")
    
    # Генерация схем
    for model_name, model_class in models.items():
        try:
            schema = model_class.model_json_schema(by_alias=by_alias)
            class_name = model_name.split('.')[-1]
            output_file = output_dir / f"{class_name}.json"
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=indent, ensure_ascii=False)
                
            print(f"✅ {class_name} -> {output_file}")
            
        except Exception as e:
            print(f"❌ Ошибка генерации схемы для {class_name}: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Генерация JSON Schema из Pydantic моделей"
    )
    parser.add_argument(
        "models_path",
        help="Путь к папке с моделями"
    )
    parser.add_argument(
        "-o", "--output",
        default="./jsonschemas",
        help="Папка для сохранения JSON Schema"
    )
    parser.add_argument(
        "-r", "--root",
        help="Корень проекта (если не указан, будет определен автоматически)"
    )
    parser.add_argument(
        "--no-alias",
        action="store_false",
        dest="by_alias",
        help="Использовать имена полей вместо алиасов"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Подробный вывод"
    )
    
    args = parser.parse_args()
    
    generate_json_schemas(
        models_path=args.models_path,
        output_dir=args.output,
        project_root=args.root,
        by_alias=args.by_alias,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()