from domains.management.commands.models import (
    CatchupCurvesCommand,
    LoadCurvesCommand,
    LoadDailyCurvesCommand,
)
from domains.management.services.loaders.curve_loader import CurveLoader
from infrastructure.db.session_management import SessionContext
from shared.cqrs.core import CommandContext, CommandHandler, CommandResult


class LoadCurvesCommandHandler(CommandHandler[LoadCurvesCommand]):
    """Обработчик команды загрузки кривых на дату.

    Использует CurveLoader для автоматической маршрутизации:
    - Кривые без datasource/dataset → CurveDbLoader (SQL БД)
    - Кривые с datasource/dataset → CurveHiveDataLoader (файлы)
    """

    def __init__(self, logger, data_context: SessionContext):
        super().__init__(logger)
        self.data_context = data_context

    def execute(self, command: LoadCurvesCommand, _):
        result = CurveLoader(self.logger, self.data_context).load_curves(
            command.date, curves_mask=command.curves_pattern, curves=command.curves or None
        )
        return CommandResult.from_service_result(None)


