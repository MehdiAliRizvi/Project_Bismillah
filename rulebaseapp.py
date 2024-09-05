from flask import current_app
from rule import Rule

class RulebaseApp:
    def __init__(self, db):
        self.collection = db.get_collection('Rulebase')

    def save_rule(self, rule):
        current_app.logger.info(f'Saving rule: {rule}')
        self.collection.insert_one(rule.to_dict())

    def get_all_rules(self):
        return [Rule.from_dict(rule) for rule in self.collection.find()]
