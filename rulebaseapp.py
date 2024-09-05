from flask import current_app
from bson import ObjectId
from rule import Rule

class RulebaseApp:
    def __init__(self, db):
        self.collection = db.get_collection('Rulebase')

    def save_rule(self, rule):
        current_app.logger.info(f'Saving rule: {rule}')
        self.collection.insert_one(rule.to_dict())

    def get_all_rules(self):
        return [Rule.from_dict(rule) for rule in self.collection.find()]

    # def update_rule(self, rule_id, rule):
    #     self.collection.update_one({'_id': rule_id}, {'$set': rule.to_dict()})

    # def delete_rule(self, rule_id):
    #     self.collection.delete_one({'_id': rule_id})