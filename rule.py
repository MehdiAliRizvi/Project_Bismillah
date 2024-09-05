from condition import Condition
from bson import ObjectId

class Rule:
    def __init__(self, category, disease_name, disease_code, rules, _id=None):
        self.category = category
        self.disease_name = disease_name
        self.disease_code = disease_code
        self.rules = rules


    def to_dict(self):
        return {
            'category': self.category,
            'disease_name': self.disease_name,
            'disease_code': self.disease_code,
            'rules': [rule.to_dict() for rule in self.rules]
        }

    @staticmethod
    def from_dict(rule_data):
        rules = [RuleEntry.from_dict(rule_entry) for rule_entry in rule_data.get('rules', [])]
        return Rule(
            rule_data.get('category'),
            rule_data.get('disease_name'),
            rule_data.get('disease_code'),
            rules
        )

class RuleEntry:
    def __init__(self, rule_id, conditions):
        self.rule_id = rule_id
        self.conditions = conditions

    def to_dict(self):
        return {
            'rule_id': self.rule_id,
            'conditions': [condition.to_dict() for condition in self.conditions]
        }

    @staticmethod
    def from_dict(rule_entry_data):
        conditions = [Condition.from_dict(condition) for condition in rule_entry_data.get('conditions', [])]
        return RuleEntry(
            rule_entry_data.get('rule_id'),
            conditions
        )