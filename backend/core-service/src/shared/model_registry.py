# from typing import Generic, TypeVar, Type


# TModel = TypeVar("TModel")
# TRepository = TypeVar("TRepository")
# TImplementation = TypeVar("TImplementation")


# class ModelServiceRegistry(Generic[TImplementation]):
#     """Фабрика репо. Использование: 
#     - Зарегистрировать типы репозиториев через add_repository_type(model_type, repo_type)
#     - Получить инстанс через create
#     """

#     def __init__(self):
#         self._registered_type_mappings = {}
#         self._registered_instances = {}


#     def register(self, cls: Type[TModel], cls_repository: Type[TImplementation]):
#         self._registered_type_mappings[cls] = cls_repository

#     #def create_repository(self, cls: Type[TModel], *args) -> GenericRepository[TModel]:

#     def get_or_create(self, cls: Type[TModel], *args) -> TImplementation[TModel]:

#         ret_val = self._registered_instances.get(cls)
        
#         # todo: вернуться сюда если будем multithreading
#         if ret_val is None:
#             repo_type = self._registered_type_mappings.get(cls)
#             if not repo_type:
#                 raise NotImplementedError()
#             ret_val = repo_type(*args)
#             self._registered_instances[cls] = ret_val

#         return ret_val
    
    