from typing import Dict, List
from domains.risk.models.contract import Contract
from domains.risk.models.curve import CurveDefinition
from domains.risk.repositories.curve_definition_data import CurveDefinitionDataObjects


class CurveDefinitionDataObjectsMock(CurveDefinitionDataObjects):
    """-"""

    def __init__(self, session = None, auto_commit = True):
        #super().__init__(session, auto_commit)
        self.cache: Dict[str, CurveDefinition] = {}

    def update(self, model, entity_find_func = None):
        self.cache[model.name] = model

    def get_all(self, scenario = None) -> List[CurveDefinition]:
        return self.cache.values()
    
    def get_first(self, slug_or_name, scenario = None) -> Contract:
        return self.cache.get(slug_or_name)
    
        
