#from domains.management.models.gl_tree import GlTreeModel
#from domains.management.repositories.gl_tree_repository import GlTreeRepository
from shared.repositories.repository_factory import RepositoryFactory

# рассматриваем как аналог application-level DI factory для данных
repository_factory = RepositoryFactory()


def register_repositories():

    # import сделан не на верхнем уровне специально. Эмулируем регистрацию и lazy load DI
    #repository_factory.register(GlTreeModel, GlTreeRepository)
    pass