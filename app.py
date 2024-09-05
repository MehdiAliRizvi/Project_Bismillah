from pymongo import MongoClient
from flask import Flask, request, jsonify, render_template, redirect, url_for
import datetime
import logging
from bson import ObjectId
from abc import ABC, abstractmethod

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

class MongoDB:
    def __init__(self, uri, db_name):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def get_collection(self, collection_name):
        return self.db[collection_name]

class RulebaseApp:
    def __init__(self, db):
        self.collection = db.get_collection('Rulebase')

    def save_rule(self, rule):
        app.logger.info(f'Saving rule: {rule}')
        self.collection.insert_one(rule.to_dict())

    def get_all_rules(self):
        return [Rule.from_dict(rule) for rule in self.collection.find()]

    def update_rule(self, rule_id, rule):
        self.collection.update_one({'_id': rule_id}, {'$set': rule.to_dict()})

    def delete_rule(self, rule_id):
        self.collection.delete_one({'_id': rule_id})

class Condition(ABC):
    @abstractmethod
    def evaluate(self, patient_age, patient_gender, lab_values):
        pass

class Condition(ABC):
    @abstractmethod
    def evaluate(self, patient_age, patient_gender, lab_values):
        pass

    @staticmethod
    def from_dict(condition_data):
        condition_type = condition_data.get('type')
        # Normalize condition type strings
        if condition_type == 'timedependent':
            condition_type = 'time-dependent'

        if condition_type == 'range':
            return RangeCondition(condition_data)
        elif condition_type == 'comparison':
            return ComparisonCondition(condition_data)
        elif condition_type == 'time-dependent':
            return TimeDependentCondition(condition_data)
        else:
            raise ValueError(f"Unknown condition type: {condition_type}")

    def to_dict(self):
        return {
            'type': self.__class__.__name__.lower().replace('condition', ''),
            'parameter': self.parameter,
            'unit': self.unit,
            'age_min': self.age_min,
            'age_max': self.age_max,
            'gender': self.gender
        }

class RangeCondition(Condition):
    def __init__(self, condition_data):
        self.min_value = condition_data.get('min_value')
        self.max_value = condition_data.get('max_value')
        self.parameter = condition_data.get('parameter')
        self.unit = condition_data.get('unit')
        self.age_min = condition_data.get('age_min')
        self.age_max = condition_data.get('age_max')
        self.gender = condition_data.get('gender')

    def evaluate(self, patient_age, patient_gender, lab_values):
        if not (self.age_min <= patient_age <= self.age_max):
            return False
        if self.gender != 'all' and self.gender != patient_gender:
            return False

        for lab_value in lab_values:
            if lab_value['parameter_name'].lower() == self.parameter.lower() and lab_value['valid_until'] >= str(datetime.date.today()):
                if self.min_value <= lab_value['value'] <= self.max_value:
                    return True
        return False

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'min_value': self.min_value,
            'max_value': self.max_value
        })
        return data

class ComparisonCondition(Condition):
    def __init__(self, condition_data):
        self.operator = condition_data.get('operator')
        self.comparison_value = condition_data.get('comparison_value')
        self.parameter = condition_data.get('parameter')
        self.unit = condition_data.get('unit')
        self.age_min = condition_data.get('age_min')
        self.age_max = condition_data.get('age_max')
        self.gender = condition_data.get('gender')

    def evaluate(self, patient_age, patient_gender, lab_values):
        if not (self.age_min <= patient_age <= self.age_max):
            return False
        if self.gender != 'all' and self.gender != patient_gender:
            return False

        for lab_value in lab_values:
            if lab_value['parameter_name'].lower() == self.parameter.lower() and lab_value['valid_until'] >= str(datetime.date.today()):
                if self.compare_values(lab_value['value']):
                    return True
        return False

    def compare_values(self, value):
        if self.operator == 'greater':
            return value > self.comparison_value
        elif self.operator == 'less':
            return value < self.comparison_value
        elif self.operator == 'equal':
            return value == self.comparison_value
        elif self.operator == 'greater or equal':
            return value >= self.comparison_value
        elif self.operator == 'less or equal':
            return value <= self.comparison_value
        return False

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'operator': self.operator,
            'comparison_value': self.comparison_value
        })
        return data

class TimeDependentCondition(Condition):
    def __init__(self, condition_data):
        self.operator = condition_data.get('operator')
        self.comparison_time_value = condition_data.get('comparison_time_value')
        self.time = condition_data.get('time')
        self.parameter = condition_data.get('parameter')
        self.unit = condition_data.get('unit')
        self.age_min = condition_data.get('age_min')
        self.age_max = condition_data.get('age_max')
        self.gender = condition_data.get('gender')

    def evaluate(self, patient_age, patient_gender, lab_values):
        if not (self.age_min <= patient_age <= self.age_max):
            return False
        if self.gender != 'all' and self.gender != patient_gender:
            return False

        relevant_lab_values = [
            lv for lv in lab_values
            if lv['parameter_name'].lower() == self.parameter.lower()
        ]

        relevant_lab_values.sort(key=lambda x: datetime.datetime.strptime(x['time'], '%Y-%m-%d'))

        if len(relevant_lab_values) < 2:
            return False

        for i in range(len(relevant_lab_values) - 1):
            for j in range(i + 1, len(relevant_lab_values)):
                time_diff = (datetime.datetime.strptime(relevant_lab_values[j]['time'], '%Y-%m-%d') -
                             datetime.datetime.strptime(relevant_lab_values[i]['time'], '%Y-%m-%d')).days

                if time_diff >= int(self.time):
                    if self.compare_values(relevant_lab_values[i]['value']) and \
                       self.compare_values(relevant_lab_values[j]['value']):
                        return True
        return False

    def compare_values(self, value):
        if self.operator == 'greater':
            return value > self.comparison_time_value
        elif self.operator == 'less':
            return value < self.comparison_time_value
        elif self.operator == 'equal':
            return value == self.comparison_time_value
        elif self.operator == 'greater or equal':
            return value >= self.comparison_time_value
        elif self.operator == 'less or equal':
            return value <= self.comparison_time_value
        return False

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'operator': self.operator,
            'comparison_time_value': self.comparison_time_value,
            'time': self.time
        })
        return data
    



class Rule:
    def __init__(self, category, disease_name, disease_code, rules):
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

# Initialize MongoDB client and access the Project1 database
try:
    mongo_db = MongoDB('mongodb://localhost:27017', 'Project1')
    rulebase_app = RulebaseApp(mongo_db)
    lab_input_user_values_collection = mongo_db.get_collection('Lab_Input_User_Values')
except Exception as e:
    app.logger.error(f"Error connecting to MongoDB: {e}")
    exit(1)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/rulebase', methods=['GET', 'POST'])
def rulebase():
    if request.method == 'POST':
        try:
            disease_category = request.form.get('category')
            disease_names = request.form.getlist('disease_names[]')
            disease_codes = request.form.getlist('disease_codes[]')
            conditions = request.form.to_dict(flat=False)

            rules_data = []

            for i in range(len(disease_names)):
                disease_entry = {
                    'category': disease_category,
                    'disease_name': disease_names[i],
                    'disease_code': disease_codes[i],
                    'rules': []
                }

                rule_index = 1
                while f'conditions[{rule_index}][]' in conditions:
                    rule_entry = {
                        'rule_id': rule_index,
                        'conditions': []
                    }

                    for condition_index in range(len(conditions[f'conditions[{rule_index}][]'])):
                        condition_type = conditions[f'conditions[{rule_index}][]'][condition_index]
                        parameter = conditions[f'parameters[{rule_index}][]'][condition_index]
                        unit = conditions[f'units[{rule_index}][]'][condition_index]
                        age_min = conditions[f'age_min[{rule_index}][]'][condition_index]
                        age_max = conditions[f'age_max[{rule_index}][]'][condition_index]
                        gender = conditions[f'genders[{rule_index}][]'][condition_index]

                        condition_entry = {
                            'type': condition_type,
                            'parameter': parameter,
                            'unit': unit,
                            'age_min': int(age_min) if age_min else None,
                            'age_max': int(age_max) if age_max else None,
                            'gender': gender
                        }

                        if condition_type == 'range':
                            min_value = conditions[f'min_values[{rule_index}][]'][condition_index]
                            max_value = conditions[f'max_values[{rule_index}][]'][condition_index]
                            condition_entry.update({
                                'min_value': float(min_value) if min_value else None,
                                'max_value': float(max_value) if max_value else None
                            })
                        elif condition_type == 'comparison':
                            operator = conditions[f'operators[{rule_index}][]'][condition_index]
                            comparison_value = conditions[f'comparison_values[{rule_index}][]'][condition_index]
                            condition_entry.update({
                                'operator': operator,
                                'comparison_value': float(comparison_value) if comparison_value else None
                            })
                        elif condition_type == 'time-dependent':
                            operator = conditions[f'operators[{rule_index}][]'][condition_index]
                            comparison_time_value = conditions[f'comparison_time_values[{rule_index}][]'][condition_index]
                            time = conditions[f'time_values[{rule_index}][]'][condition_index]
                            condition_entry.update({
                                'operator': operator,
                                'comparison_time_value': float(comparison_time_value) if comparison_time_value else None,
                                'time': time
                            })

                        rule_entry['conditions'].append(condition_entry)

                    disease_entry['rules'].append(rule_entry)
                    rule_index += 1

                rules_data.append(disease_entry)

            for rule_data in rules_data:
                rule = Rule(
                    rule_data['category'],
                    rule_data['disease_name'],
                    rule_data['disease_code'],
                    [RuleEntry.from_dict(rule_entry) for rule_entry in rule_data['rules']]
                )
                rulebase_app.save_rule(rule)

            return jsonify({'message': 'Rules successfully added to the database'}), 200

        except Exception as e:
            app.logger.error(f'Error adding data: {str(e)}')
            return jsonify({'message': f'Error adding data: {str(e)}'}), 500

    return render_template('rulebase.html')

@app.route('/lab_values', methods=['GET', 'POST'])
def lab_values():
    if request.method == 'POST':
        try:
            patient_id = request.form.get('patient-id')
            age = int(request.form.get('age'))
            gender = request.form.get('gender')
            parameters = request.form.getlist('parameter-name')
            values = request.form.getlist('value')
            units = request.form.getlist('unit')
            valid_untils = request.form.getlist('valid-until')
            times = request.form.getlist('time-lab-value')
            lab_values_data = []
            for i in range(len(parameters)):
                lab_value_data = {
                    'parameter_name': parameters[i],
                    'value': float(values[i]),
                    'unit': units[i],
                    'valid_until': valid_untils[i],
                    'time': times[i]
                }
                lab_values_data.append(lab_value_data)

            existing_patient = lab_input_user_values_collection.find_one({'patient_id': patient_id})
            if existing_patient:
                lab_input_user_values_collection.update_one(
                    {'patient_id': patient_id},
                    {'$push': {'lab_values': {'$each': lab_values_data}}}
                )
            else:
                new_patient_data = {
                    'patient_id': patient_id,
                    'age': age,
                    'gender': gender,
                    'lab_values': lab_values_data
                }
                lab_input_user_values_collection.insert_one(new_patient_data)

            matching_diseases = evaluate_lab_values(age, gender, lab_values_data)

            if matching_diseases:
                return jsonify({'status': 'success', 'message': 'Lab values saved and evaluated successfully!', 'results': matching_diseases})
            else:
                return jsonify({'status': 'success', 'message': 'Lab values saved successfully! No disease match found.', 'results': []})
        except Exception as e:
            app.logger.error(f"Error occurred while saving lab values: {e}")
            return jsonify({'status': 'error', 'message': str(e)})
    return render_template('lab_values.html')

def evaluate_lab_values(patient_age, patient_gender, lab_values):
    try:
        rules = rulebase_app.get_all_rules()

        matching_diseases = []

        for rule in rules:
            for rule_entry in rule.rules:
                rule_conditions_met = True
                for condition in rule_entry.conditions:
                    if not condition.evaluate(patient_age, patient_gender, lab_values):
                        rule_conditions_met = False
                        break
                if rule_conditions_met:
                    matching_diseases.append({
                        'disease_code': rule.disease_code,
                        'disease_name': rule.disease_name,
                        'category': rule.category,
                        'matching_rule': rule_entry.to_dict()
                    })
                    break  # Since rules are OR-ed, we can stop checking further rules for this disease

        return matching_diseases
    except Exception as e:
        print(f"Error occurred while evaluating lab values: {e}")
        return []

@app.route('/view_rulebase', methods=['GET'])
def view_rulebase():
    try:
        rules = rulebase_app.get_all_rules()
        return render_template('view_rulebase.html', rules=[rule.to_dict() for rule in rules])
    except Exception as e:
        app.logger.error(f'Error fetching rules: {str(e)}')
        return jsonify({'message': f'Error fetching rules: {str(e)}'}), 500

@app.route('/edit_rule/<rule_id>', methods=['GET', 'POST'])
def edit_rule(rule_id):
    try:
        rule = rulebase_app.collection.find_one({'_id': ObjectId(rule_id)})
        if request.method == 'POST':
            updated_rule = {
                'category': request.form.get('category'),
                'disease_name': request.form.get('disease_name'),
                'disease_code': request.form.get('disease_code'),
                'rules': []
            }

            disease_names = request.form.getlist('disease_names[]')
            disease_codes = request.form.getlist('disease_codes[]')
            conditions = request.form.to_dict(flat=False)

            for i in range(len(disease_names)):
                disease_entry = {
                    'category': updated_rule['category'],
                    'disease_name': disease_names[i],
                    'disease_code': disease_codes[i],
                    'rules': []
                }

                rule_index = 1
                while f'conditions[{rule_index}][]' in conditions:
                    rule_entry = {
                        'rule_id': rule_index,
                        'conditions': []
                    }

                    for condition_index in range(len(conditions[f'conditions[{rule_index}][]'])):
                        condition_type = conditions[f'conditions[{rule_index}][]'][condition_index]
                        parameter = conditions[f'parameters[{rule_index}][]'][condition_index]
                        unit = conditions[f'units[{rule_index}][]'][condition_index]
                        age_min = conditions[f'age_min[{rule_index}][]'][condition_index]
                        age_max = conditions[f'age_max[{rule_index}][]'][condition_index]
                        gender = conditions[f'genders[{rule_index}][]'][condition_index]

                        condition_entry = {
                            'type': condition_type,
                            'parameter': parameter,
                            'unit': unit,
                            'age_min': int(age_min) if age_min else None,
                            'age_max': int(age_max) if age_max else None,
                            'gender': gender
                        }

                        if condition_type == 'range':
                            min_value = conditions[f'min_values[{rule_index}][]'][condition_index]
                            max_value = conditions[f'max_values[{rule_index}][]'][condition_index]
                            condition_entry.update({
                                'min_value': float(min_value) if min_value else None,
                                'max_value': float(max_value) if max_value else None
                            })
                        elif condition_type == 'comparison':
                            operator = conditions[f'operators[{rule_index}][]'][condition_index]
                            comparison_value = conditions[f'comparison_values[{rule_index}][]'][condition_index]
                            condition_entry.update({
                                'operator': operator,
                                'comparison_value': float(comparison_value) if comparison_value else None
                            })
                        elif condition_type == 'time-dependent':
                            operator = conditions[f'operators[{rule_index}][]'][condition_index]
                            comparison_time_value = conditions[f'comparison_time_values[{rule_index}][]'][condition_index]
                            time = conditions[f'time_values[{rule_index}][]'][condition_index]
                            condition_entry.update({
                                'operator': operator,
                                'comparison_time_value': float(comparison_time_value) if comparison_time_value else None,
                                'time': time
                            })

                        rule_entry['conditions'].append(condition_entry)

                    disease_entry['rules'].append(rule_entry)
                    rule_index += 1

                updated_rule['rules'].append(disease_entry)

            rulebase_app.update_rule(ObjectId(rule_id), Rule.from_dict(updated_rule))
            return redirect(url_for('view_rulebase'))
        return render_template('edit_rule.html', rule=rule)
    except Exception as e:
        app.logger.error(f'Error editing rule: {str(e)}')
        return jsonify({'message': f'Error editing rule: {str(e)}'}), 500

@app.route('/delete_rule/<rule_id>', methods=['POST'])
def delete_rule(rule_id):
    try:
        rulebase_app.delete_rule(ObjectId(rule_id))
        return redirect(url_for('view_rulebase'))
    except Exception as e:
        app.logger.error(f'Error deleting rule: {str(e)}')
        return jsonify({'message': f'Error deleting rule: {str(e)}'}), 500

if __name__ == '__main__':
    rules = rulebase_app.get_all_rules()
    app.run(debug=True)                       