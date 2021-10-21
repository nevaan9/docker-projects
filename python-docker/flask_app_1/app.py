# https://felipefaria.medium.com/running-a-simple-flask-application-inside-a-docker-container-b83bf3e07dd5
from flask import Flask, request, jsonify, make_response
from deepdiff import DeepDiff
from re import search, split

app = Flask(__name__)

def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    return response

def _corsify_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

@app.route('/')
def hello_world():
    return 'Hey, we have Flask in a Docker container!'

@app.route('/compare', methods=["POST", "OPTIONS"])
def add_message():
    if request.method == "OPTIONS": # CORS preflight
        return _build_cors_preflight_response()
    elif request.method == "POST": # The actual request following the preflight
        post_data = request.json
        
        original_structure = post_data['original_structure']
        modified_structure = post_data['modified_structure']

        # Skip over changes in FIELD UUID { fields: 0: { uuid: 123-6543-2332 } } --- root['fields']['0']['uuid']
        field_uuid_pattern = '^root\[\'fields\'\]\[\'(\d+)\'\]\[\'uuid\'\]$'

        def exclude_obj_callback(obj, path):
            return True if search(field_uuid_pattern, path) else False

        diff = DeepDiff(original_structure, modified_structure, view='tree', get_deep_distance=True, exclude_obj_callback=exclude_obj_callback)

        distance = diff.get('deep_distance') or 0

        field_changes = {}
        form_changes = {}
        removed_fields = []
        added_fields = []

        # Just get the changes from the diff object in a tree structure so we can traverse/manipulate it
        dic_items_added = diff.get('dictionary_item_added') or []
        dic_items_removed = diff.get('dictionary_item_removed') or []
        dic_items_changed = diff.get('values_changed') or []
        arr_items_added = diff.get('iterable_item_added') or []
        arr_items_removed = diff.get('iterable_item_removed') or []
        types_changed = diff.get('type_changes') or []

        # path deconstructor pattern
        path_deconstructor_pattern = r"[^a-zA-Z0-9-_]+"

        # Patterns to match what changed
        field_pattern = '^root\[\'fields\'\]\[\'(\d+)\'\]'
        field_root_pattern = '^root\[\'fields\'\]\[\'(\d+)\'\]$'
        field_setting_changed_pattern = '^root\[\'fields\'\]\[\'(\d+)\'\]\[\'([a-zA-Z0-9-_]+)\'\]$'
        field_properties_changed_pattern = '^root\[\'fields\'\]\[\'(\d+)\'\]\[\'properties\'\]\[\'([a-z\-?\d?A-Z09]+)\'\]$'
        field_rules_changed_pattern = '^root\[\'fields\'\]\[\'(\d+)\'\]\[\'rules\'\]\[(\d+)\]\[\'([a-zA-Z09]+)\'\]$'
        field_rules_add_pattern = '^root\[\'fields\'\]\[\'(\d+)\'\]\[\'rules\'\]\[(\d+)\]$'

        # if its not in the original structure, its in the modified one
        def getField(f_index):
            try:
                return original_structure['fields'][f_index]
            except:
                return modified_structure['fields'][f_index]


        def populate_field_changes_object(f_index):
            field = getField(f_index)
            field_changes[f_index] = {
                'name': field.get('name'),
                'fieldType': field.get('fieldType'),
                'index': f_index,
                'fieldId': field.get('fieldId')
            }

        def getRule(r_index, f_index):
            field = getField(f_index)
            rule_index = int(r_index)
            return field['rules'][rule_index]

        # Added iterable Items
        for arr_add in arr_items_added:
            path = arr_add.path()
            # Check if it's a form field value
            field_match = search(field_pattern, path)
            if (field_match):
                # Get the field index
                field_index = field_match.group(1)
                # Populate some useful field info into field_changes object
                if field_index not in field_changes:
                    populate_field_changes_object(field_index)
                field_rules_add_match = search(field_rules_add_pattern, path)
                if (field_rules_add_match):
                    # Add a addedRules arr if the field does not have it
                    if ('addedRules' not in field_changes[field_index]):
                        field_changes[field_index]['addedRules'] = []
                    # Get the rule details
                    rule_index = field_rules_add_match.group(2)
                    field_changes[field_index]['addedRules'].append({ 'ruleIndex': rule_index, 'rule': arr_add.t2 })
                else:
                    # Not a rule? Add it to 'iterableAdded'
                    if ('iterableAdded' not in field_changes[field_index]):
                        field_changes[field_index]['iterableAdded'] = []
                    # No match we found in field setting, field properties, field rules - return to the client the full path
                    path_split = split(path_deconstructor_pattern, path)
                    path_arr = path_split[1:-1]
                    field_changes[field_index]['iterableAdded'].append({ 'propertyName': path, 'value': arr_add.t2, 'action': 'ADDED', 'pathArray': path_arr })
            else:
                # This is a form setting
                if ('iterableAdded' not in form_changes):
                    form_changes['iterableAdded'] = []
                path_split = split(path_deconstructor_pattern, path)
                path_arr = path_split[1:-1]
                form_changes['iterableAdded'].append({ 'propertyName': path, 'value': arr_add.t2, 'pathArray': path_arr })

        # Removed iterable Items
        for arr_remove in arr_items_removed:
            path = arr_remove.path()
            # Check if it's a form field value
            field_match = search(field_pattern, path)
            if (field_match):
                # Get the field index
                field_index = field_match.group(1)
                # Populate some useful field info into field_changes object
                if field_index not in field_changes:
                    populate_field_changes_object(field_index)
                field_rules_add_match = search(field_rules_add_pattern, path)
                if (field_rules_add_match):
                    # Add a removedRules arr if the field does not have it
                    if ('removedRules' not in field_changes[field_index]):
                        field_changes[field_index]['removedRules'] = []
                    # Get the rule details
                    rule_index = field_rules_add_match.group(2)
                    field_changes[field_index]['removedRules'].append({ 'ruleIndex': rule_index, 'rule': arr_remove.t1 })
                else:
                    # Could not parse rules? add it to iterableRemoved
                    if ('iterableRemoved' not in field_changes[field_index]):
                        field_changes[field_index]['iterableRemoved'] = []
                    # No match we found in field setting, field properties, field rules - return to the client the full path
                    path_split = split(path_deconstructor_pattern, path)
                    path_arr = path_split[1:-1]
                    field_changes[field_index]['iterableRemoved'].append({ 'propertyName': path, 'value': arr_remove.t1, 'action': 'REMOVED', 'pathArray': path_arr })
            else:
                # This is a form setting
                if ('iterableRemoved' not in form_changes):
                    form_changes['iterableRemoved'] = []
                path_split = split(path_deconstructor_pattern, path)
                path_arr = path_split[1:-1]
                form_changes['iterableRemoved'].append({ 'propertyName': path, 'value': arr_remove.t1, 'pathArray': path_arr })

        # Removed Field Properties
        for remove in dic_items_removed:
            path = remove.path()
            # Check if it's a form field value
            field_match = search(field_pattern, path)
            if (field_match):
                # Get the field index
                field_index = field_match.group(1)
                # First things first -- check if the entire field was removed
                field_root_match = search(field_root_pattern, path)
                if (field_root_match):
                    field = getField(field_index)
                    removed_fields.append({ 'name': field.get('name'), 'fieldType': field.get('fieldType'), 'index': field_index, 'fieldId': field.get('fieldId') })
                else:
                    # Populate some useful field info into field_changes object
                    if field_index not in field_changes:
                        populate_field_changes_object(field_index)
                    # Add a removedProperties arr if the field does not have it
                    if ('removedProperties' not in field_changes[field_index]):
                        field_changes[field_index]['removedProperties'] = []
                    field_setting_changed_match = search(field_setting_changed_pattern, path)
                    field_properties_changed_match = search(field_properties_changed_pattern, path)
                    if (field_setting_changed_match or field_properties_changed_match):
                        # can be a top level field setting or a setting inside 'properties'
                        matchObj = field_setting_changed_match or field_properties_changed_match
                        setting_name = matchObj.group(2)
                        field_changes[field_index]['removedProperties'].append({ 'propertyName': setting_name })
                    else:
                        # No match we found in field setting, field properties, field rules - return to the client the full path
                        path_split = split(path_deconstructor_pattern, path)
                        path_arr = path_split[1:-1]
                        field_changes[field_index]['removedProperties'].append({ 'propertyName': path, 'pathArray': path_arr })
            else:
                # This is a form setting
                if ('removedProperties' not in form_changes):
                    form_changes['removedProperties'] = []
                path_split = split(path_deconstructor_pattern, path)
                path_arr = path_split[1:-1]
                form_changes['removedProperties'].append({ 'propertyName': path, 'pathArray': path_arr })

        # Added Field Properties
        for add in dic_items_added:
            path = add.path()
            # Check if it's a form field value
            field_match = search(field_pattern, path)
            if (field_match):
                # Get the field index
                field_index = field_match.group(1)
                # First things first -- check if an entire field was added
                field_root_match = search(field_root_pattern, path)
                if (field_root_match):
                    field = getField(field_index)
                    added_fields.append({ 'name': field.get('name'), 'fieldType': field.get('fieldType'), 'index': field_index, 'fieldId': field.get('fieldId') })
                else:
                    # Populate some useful field info into field_changes object
                    if field_index not in field_changes:
                        populate_field_changes_object(field_index)
                    # Add a addedProperties arr if the field does not have it
                    if ('addedProperties' not in field_changes[field_index]):
                        field_changes[field_index]['addedProperties'] = [] 
                    field_setting_changed_match = search(field_setting_changed_pattern, path)
                    field_properties_changed_match = search(field_properties_changed_pattern, path)
                    if (field_setting_changed_match or field_properties_changed_match):
                        # can be a top level field setting or a setting inside 'properties'
                        matchObj = field_setting_changed_match or field_properties_changed_match
                        setting_name = matchObj.group(2)
                        field_changes[field_index]['addedProperties'].append({ 'propertyName': setting_name })
                    else:
                        # No match we found in field setting, field properties, field rules - return to the client the full path
                        path_split = split(path_deconstructor_pattern, path)
                        path_arr = path_split[1:-1]
                        field_changes[field_index]['addedProperties'].append({ 'propertyName': path, 'pathArray': path_arr })
            else:
                # This is a form setting
                if ('addedProperties' not in form_changes):
                    form_changes['addedProperties'] = []
                path_split = split(path_deconstructor_pattern, path)
                path_arr = path_split[1:-1]
                form_changes['addedProperties'].append({ 'propertyName': path, 'pathArray': path_arr })

        # Changed Field Properties
        for change in dic_items_changed:
            path = change.path()
            # Check if it's a form field value
            field_match = search(field_pattern, path)
            if (field_match):
                # Get the field index
                field_index = field_match.group(1)
                # Populate some useful field info into field_changes object
                if field_index not in field_changes:
                    populate_field_changes_object(field_index)
                # Add a changedProperties arr if the field does not have it
                if ('changedProperties' not in field_changes[field_index]):
                    field_changes[field_index]['changedProperties'] = [] 
                field_setting_changed_match = search(field_setting_changed_pattern, path)
                field_properties_changed_match = search(field_properties_changed_pattern, path)
                field_rules_changed_match = search(field_rules_changed_pattern, path)
                if (field_setting_changed_match or field_properties_changed_match):
                    # can be a top level field setting or a setting inside 'properties'
                    matchObj = field_setting_changed_match or field_properties_changed_match
                    setting_name = matchObj.group(2)
                    field_changes[field_index]['changedProperties'].append({ 'propertyName': setting_name, 'oldValue': change.t1, 'newValue': change.t2 })
                elif (field_rules_changed_match):
                    # Add a changedRules arr if the field does not have it
                    if ('changedRules' not in field_changes[field_index]):
                        field_changes[field_index]['changedRules'] = {}
                    # Get the rule details
                    rule_index = field_rules_changed_match.group(2)
                    rule_setting = field_rules_changed_match.group(3)
                    rule = getRule(rule_index, field_index)
                    if (rule_index not in field_changes[field_index]['changedRules']):
                        field_changes[field_index]['changedRules'][rule_index] = {
                            'ruleIndex': rule_index,
                            'type': rule.get('type'),
                            'changedProperties': [],
                            'addedProperties': [],
                            'removedProperties': [],
                        }
                    field_changes[field_index]['changedRules'][rule_index]['changedProperties'].append({ 'propertyName': rule_setting, 'oldValue': change.t1, 'newValue': change.t2 })
                else:
                    # No match we found in field setting, field properties, field rules - return to the client the full path
                    path_split = split(path_deconstructor_pattern, path)
                    path_arr = path_split[1:-1]
                    field_changes[field_index]['changedProperties'].append({ 'propertyName': path, 'oldValue': change.t1, 'newValue': change.t2, 'pathArray': path_arr })
            else:
                # This is a form setting
                if ('changedProperties' not in form_changes):
                    form_changes['changedProperties'] = []
                path_split = split(path_deconstructor_pattern, path)
                path_arr = path_split[1:-1]
                form_changes['changedProperties'].append({ 'propertyName': path, 'oldValue': change.t1, 'newValue': change.t2, 'pathArray': path_arr })

        for change in types_changed:
            path = change.path()
            # Check if it's a form field value
            field_match = search(field_pattern, path)
            if (field_match):
                # Get the field index
                field_index = field_match.group(1)
                # Populate some useful field info into field_changes object
                if field_index not in field_changes:
                    populate_field_changes_object(field_index)
                # Add a changedProperties arr if the field does not have it
                if ('changedProperties' not in field_changes[field_index]):
                    field_changes[field_index]['changedProperties'] = [] 
                field_setting_changed_match = search(field_setting_changed_pattern, path)
                field_properties_changed_match = search(field_properties_changed_pattern, path)
                field_rules_changed_match = search(field_rules_changed_pattern, path)
                if (field_setting_changed_match or field_properties_changed_match):
                    # can be a top level field setting or a setting inside 'properties'
                    matchObj = field_setting_changed_match or field_properties_changed_match
                    setting_name = matchObj.group(2)
                    field_changes[field_index]['changedProperties'].append({ 'propertyName': setting_name, 'oldValue': change.t1, 'newValue': change.t2 })
                elif (field_rules_changed_match):
                    # Add a changedRules arr if the field does not have it
                    if ('changedRules' not in field_changes[field_index]):
                        field_changes[field_index]['changedRules'] = {}
                    # Get the rule details
                    rule_index = field_rules_changed_match.group(2)
                    rule_setting = field_rules_changed_match.group(3)
                    rule = getRule(rule_index, field_index)
                    if (rule_index not in field_changes[field_index]['changedRules']):
                        field_changes[field_index]['changedRules'][rule_index] = {
                            'ruleIndex': rule_index,
                            'type': rule.get('type'),
                            'changedProperties': [],
                            'addedProperties': [],
                            'removedProperties': [],
                        }
                    field_changes[field_index]['changedRules'][rule_index]['changedProperties'].append({ 'propertyName': rule_setting, 'oldValue': change.t1, 'newValue': change.t2 })
                else:
                    # No match we found in field setting, field properties, field rules - return to the client the full path
                    path_split = split(path_deconstructor_pattern, path)
                    path_arr = path_split[1:-1]
                    field_changes[field_index]['changedProperties'].append({ 'propertyName': path, 'oldValue': change.t1, 'newValue': change.t2, 'pathArray': path_arr })
            else:
                # This is a form setting
                if ('changedProperties' not in form_changes):
                    form_changes['changedProperties'] = []
                path_split = split(path_deconstructor_pattern, path)
                path_arr = path_split[1:-1]
                form_changes['changedProperties'].append({ 'propertyName': path, 'oldValue': change.t1, 'newValue': change.t2, 'pathArray': path_arr })
                

        return _corsify_actual_response(jsonify({ 'fieldChanges': field_changes, 'changeDistance': round(distance * 100, 2) }))
    else:
        raise RuntimeError("Weird - don't know how to handle method {}".format(request.method))

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
