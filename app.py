from flask import Flask, request, jsonify, render_template, redirect, url_for
import logging
from bson import ObjectId
from mongodb import MongoDB
from rulebaseapp import RulebaseApp
from rule import Rule, RuleEntry
from condition import Condition


app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

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

            return jsonify({'status': 'success', 'message': 'Rules successfully added to the database'}), 200

        except Exception as e:
            app.logger.error(f'Error adding data: {str(e)}')
            return jsonify({'status': 'error', 'message': f'Error adding data: {str(e)}'}), 500

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
    render_template('rulebase.html')

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