# infrastructure/db/models/all.py
# нужен для алембика — импортирует все ORM-модули, чтобы Base.metadata был полным
import infrastructure.db.models.audit  # noqa: F401
import infrastructure.db.models.portal  # noqa: F401
