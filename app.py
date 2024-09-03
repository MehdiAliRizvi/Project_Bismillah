from pymongo import MongoClient
from flask import Flask, request, jsonify, render_template
import datetime
import logging

app = Flask(__name__)

class MongoDB:
    def __init__(self, uri, db_name):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def get_collection(self, collection_name):
        return self.db[collection_name]

class RulebaseApp:
    def __init__(self, db):
        self.collection = db.get_collection('Rulebase')

    def save_rule(self, rule_data):
        logging.info(f'Saving rule data: {rule_data}')  # Log the data being saved
        self.collection.insert_one(rule_data)

    def get_all_rules(self):
        return list(self.collection.find())

    def update_rule(self, rule_id, rule_data):
        self.collection.update_one({'_id': rule_id}, {'$set': rule_data})

    def delete_rule(self, rule_id):
        self.collection.delete_one({'_id': rule_id})

# Initialize MongoDB client and access the Project1 database
try:
    mongo_db = MongoDB('mongodb://localhost:27017', 'Project1')
    lab_input_user_values_collection = mongo_db.get_collection('Lab_Input_User_Values')
    rulebase_app = RulebaseApp(mongo_db)
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
    exit(1)  # Exit if there's an issue connecting to the database

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/rulebase', methods=['GET', 'POST'])  # This is the rulebase.
def rulebase():
    if request.method == 'POST':
        try:
            # Extract and parse data from form
            disease_names = request.form.getlist('disease_names[]')
            disease_codes = request.form.getlist('disease_codes[]')
            conditions = request.form.to_dict(flat=False)

            # Prepare the list to store diseases and their rules
            rules_data = []

            # Log the received data
            app.logger.info(f'Received disease names: {disease_names}')
            app.logger.info(f'Received disease codes: {disease_codes}')
            app.logger.info(f'Received conditions: {conditions}')

            # Iterate over diseases to create the nested structure
            for i in range(len(disease_names)):
                disease_entry = {
                    'disease_name': disease_names[i],
                    'disease_code': disease_codes[i],
                    'rules': []
                }

                # Find the rules and conditions for this particular disease
                rule_index = 1
                while f'conditions[{rule_index}][]' in conditions:
                    rule_entry = {
                        'rule_id': rule_index,
                        'conditions': []
                    }

                    # Extract all conditions for this rule
                    condition_keys = [
                        f'conditions[{rule_index}][]',
                        f'parameters[{rule_index}][]',
                        f'units[{rule_index}][]',
                        f'age_min[{rule_index}][]',
                        f'age_max[{rule_index}][]',
                        f'genders[{rule_index}][]',
                        f'min_values[{rule_index}][]',
                        f'max_values[{rule_index}][]',
                        f'operators[{rule_index}][]',
                        f'comparison_values[{rule_index}][]',
                        f'time_values[{rule_index}][]',
                        f'operators_time[{rule_index}][]',
                        f'comparison_time_values[{rule_index}][]'
                    ]

                    # Find the maximum length of the condition lists
                    max_length = max([len(conditions[key]) for key in condition_keys if key in conditions])

                    # Pad all lists to match the maximum length
                    padded_conditions = {key: (conditions[key] + [None] * (max_length - len(conditions[key])) if key in conditions else [None] * max_length) for key in condition_keys}

                    for condition_index in range(max_length):
                        condition_type = padded_conditions[f'conditions[{rule_index}][]'][condition_index]
                        parameter = padded_conditions[f'parameters[{rule_index}][]'][condition_index]
                        unit = padded_conditions[f'units[{rule_index}][]'][condition_index]
                        age_min = padded_conditions[f'age_min[{rule_index}][]'][condition_index]
                        age_max = padded_conditions[f'age_max[{rule_index}][]'][condition_index]
                        gender = padded_conditions[f'genders[{rule_index}][]'][condition_index]

                        condition_entry = {
                            'type': condition_type,
                            'parameter': parameter,
                            'unit': unit,
                            'age_min': int(age_min) if age_min else None,
                            'age_max': int(age_max) if age_max else None,
                            'gender': gender
                        }

                        # Add fields based on condition type
                        if condition_type == 'range':
                            min_value = padded_conditions[f'min_values[{rule_index}][]'][condition_index]
                            max_value = padded_conditions[f'max_values[{rule_index}][]'][condition_index]
                            if min_value:
                                condition_entry['min_value'] = float(min_value)
                            if max_value:
                                condition_entry['max_value'] = float(max_value)
                        elif condition_type == 'comparison':
                            operator = padded_conditions[f'operators[{rule_index}][]'][condition_index]
                            comparison_value = padded_conditions[f'comparison_values[{rule_index}][]'][condition_index]
                            if operator:
                                condition_entry['operator'] = operator
                            if comparison_value:
                                condition_entry['comparison_value'] = float(comparison_value)
                        elif condition_type == 'time-dependent':
                            operator_time = padded_conditions[f'operators_time[{rule_index}][]'][condition_index]
                            comparison_time_value = padded_conditions[f'comparison_time_values[{rule_index}][]'][condition_index]
                            time = padded_conditions[f'time_values[{rule_index}][]'][condition_index]
                            if operator_time:
                                condition_entry['operator_time'] = operator_time
                            if comparison_time_value:
                                condition_entry['comparison_time_value'] = float(comparison_time_value)
                            if time:
                                condition_entry['time'] = time

                        # Log the condition entry
                        app.logger.info(f'Condition entry: {condition_entry}')

                        # Remove None values
                        condition_entry = {k: v for k, v in condition_entry.items() if v not in [None, '']}

                        # Add condition to rule
                        rule_entry['conditions'].append(condition_entry)

                    # Append the rule to the disease entry
                    disease_entry['rules'].append(rule_entry)
                    rule_index += 1

                # Append the disease entry to rules data
                rules_data.append(disease_entry)

            # Log the rules data before saving
            app.logger.info(f'Rules data to be saved: {rules_data}')

            # Insert rules data into MongoDB
            for rule in rules_data:
                rulebase_app.save_rule(rule)

            return jsonify({'message': 'Rules successfully added to the database'}), 200

        except Exception as e:
            return jsonify({'message': f'Error adding data: {str(e)}'}), 500

    return render_template('rulebase.html')  # Replace with your form template name




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
            times = request.form.getlist('time-lab-value')  # New field for time
            lab_values_data = []
            for i in range(len(parameters)):
                lab_value_data = {
                    'parameter_name': parameters[i],
                    'value': float(values[i]),
                    'unit': units[i],
                    'valid_until': valid_untils[i],
                    'time': times[i]  # Add the time field
                }
                lab_values_data.append(lab_value_data)

            # Check if a document with the same patient ID already exists
            existing_patient = lab_input_user_values_collection.find_one({'patient_id': patient_id})
            if existing_patient:
                # Update the existing document by appending new lab values
                lab_input_user_values_collection.update_one(
                    {'patient_id': patient_id},
                    {'$push': {'lab_values': {'$each': lab_values_data}}}
                )
            else:
                # Create a new document
                new_patient_data = {
                    'patient_id': patient_id,
                    'age': age,
                    'gender': gender,
                    'lab_values': lab_values_data
                }
                lab_input_user_values_collection.insert_one(new_patient_data)

            # Evaluate the lab values against the rules
            matching_diseases = evaluate_lab_values(age, gender, lab_values_data)

            if matching_diseases:

                return jsonify({'status': 'success', 'message': 'Lab values saved and evaluated successfully!', 'results': matching_diseases})
            else:
                return jsonify({'status': 'success', 'message': 'Lab values saved successfully! No disease match found.', 'results': []})
        except Exception as e:
            # Log error for debugging
            print(f"Error occurred while saving lab values: {e}")
            return jsonify({'status': 'error', 'message': str(e)})
    return render_template('lab_values.html')

 
def evaluate_lab_values(patient_age, patient_gender, lab_values):
    try:
        # Fetch all rules from the database
        rules = rulebase_app.get_all_rules()
        # print(rules)

        matching_diseases = []

        for rule in rules:
            disease_name = rule['disease_name']
            disease_code = rule['disease_code']
            for rule_entry in rule['rules']:
                rule_conditions_met = True
                for condition in rule_entry['conditions']:
                    if not evaluate_condition(condition, patient_age, patient_gender, lab_values):
                        rule_conditions_met = False
                        break
                if rule_conditions_met:
                    matching_diseases.append({
                        'disease_code': disease_code,
                        'disease_name': disease_name,
                        'matching_rule': rule_entry
                    })
                    break  # Since rules are OR-ed, we can stop checking further rules for this disease

        return matching_diseases
    except Exception as e:
        print(f"Error occurred while evaluating lab values: {e}")
        return []

def evaluate_condition(condition, patient_age, patient_gender, lab_values):
    if not (condition['age_min'] <= patient_age <= condition['age_max']):
        return False
    if condition['gender'] != 'all' and condition['gender'] != patient_gender:
        return False

    for lab_value in lab_values:
        if lab_value['parameter_name'].lower() == condition['parameter'].lower() and lab_value['valid_until'] >= str(datetime.date.today()):
            if condition['type'] == 'range':
                if not (condition['min_value'] <= lab_value['value'] <= condition['max_value']):
                    return False
            elif condition['type'] == 'comparison':
                if not compare_values(lab_value['value'], condition['operator'], condition['comparison_value']):
                    return False
            elif condition['type'] == 'time-dependent':
                if not evaluate_time_condition(lab_values, condition):
                    return False
            return True
    return False

def compare_values(value, operator, comparison_value):
    if operator == 'greater':
        return value > comparison_value
    elif operator == 'less':
        return value < comparison_value
    elif operator == 'equal':
        return value == comparison_value
    elif operator == 'greater or equal':
        return value >= comparison_value
    elif operator == 'less or equal':
        return value <= comparison_value
    return False

def evaluate_time_condition(lab_values, condition):
    # Extract relevant lab values for the condition's parameter
    relevant_lab_values = [
        lv for lv in lab_values
        if lv['parameter_name'].lower() == condition['parameter'].lower()
    ]

    # Sort lab values by time
    relevant_lab_values.sort(key=lambda x: x['time'])

    # Debugging: Print relevant lab values
    # print(f"Relevant lab values for parameter '{condition['parameter']}': {relevant_lab_values}")

    # Check if there are at least two lab values to compare
    if len(relevant_lab_values) < 2:
        print("Not enough lab values to evaluate time-dependent condition.")
        return False

    # Iterate over the lab values to find pairs that meet the condition
    for i in range(len(relevant_lab_values) - 1):
        for j in range(i + 1, len(relevant_lab_values)):
            time_diff = (datetime.datetime.strptime(relevant_lab_values[j]['time'], '%Y-%m-%d') -
                         datetime.datetime.strptime(relevant_lab_values[i]['time'], '%Y-%m-%d')).days

            # Debugging: Print time difference and values being compared
            # print(f"Comparing values: {relevant_lab_values[i]['value']} and {relevant_lab_values[j]['value']}")
            # print(f"Time difference: {time_diff} days")

            if time_diff >= int(condition['time']):
                # # Debugging: Print condition details
                # print(f"Condition details: {condition}")

                if 'comparison_value' in condition:
                    if compare_values(relevant_lab_values[i]['value'], condition['operator'], condition['comparison_value']) and \
                       compare_values(relevant_lab_values[j]['value'], condition['operator'], condition['comparison_value']):
                        print("Time-dependent condition met.")
                        return True
                else:
                    print("comparison_value not found in condition.")
                    return False

    print("Time-dependent condition not met.")
    return False



 
if __name__ == '__main__':
    rules = rulebase_app.get_all_rules()
    # print(rules)
    app.run(debug=True)