from typing import Dict, List
from domains.risk.models.contract import Contract
from domains.risk.models.curve import CurveDefinition
from domains.risk.repositories.contract_data import ContractDataObjects


class ContractDataObjectsMock(ContractDataObjects):
    """-"""

    def __init__(self, session = None, auto_commit = True):
        super().__init__(session)
        self.cache: Dict[str, Contract] = {}

    def update(self, model, entity_find_func = None):
        self.cache[model.name] = model

    def get_all(self, scenario = None) -> List[Contract]:
        return self.cache.values()
    
    def get_first(self, slug_or_name, scenario = None) -> Contract:
        return self.cache.get(slug_or_name)
    
        
class ValuationRunDataContextMock():

    def __init__(self):
        self.calendars = None  
        self.curve_definitions = None 
        self.curves = None 
        self.scenarions = None 
        
