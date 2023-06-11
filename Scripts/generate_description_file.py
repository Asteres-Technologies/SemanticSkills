"""
A script to generate a description file for skills in the repo.
Uses OpenAI's GPT-4 model to generate a description for each skill.
Each skprompt.txt file in the repo is summarized and described.
A standard format in TOML for the description is used.

[description]
skill_name = "The name of the skill."
skill_description = "A 1 sentence description of the skill."
output_name = "The name of the output/result generated by the skill."
output_description = "A 1 sentence description of the output"
output_uses = "A 1 sentence description of how the output can be used."
output_type = "The type of output, such as raw test, list as a string, number as a string, json, toml, xml, etc. as mime types. Invented types are allowed."
[[arguments]]
argument_name = "The name of the argument."
argument_identifier = "{{argument_name}}"
argument_description = "A 1 sentence description of the argument."
argument_sources = "A 1 sentence description of where the argument could come from."
argument_type = "The expected type of the argument, such as string, number, list, etc. as mime types. Invented types are allowed."

The description file is saved in the same directory as the skprompt.txt file as skill_description.toml.
"""
from ruamel.yaml.scalarstring import PreservedScalarString
from dotenv import dotenv_values
import ruamel.yaml as yaml
import os, sys, argparse, re
import toml
import openai

def validate_description_generation(description_toml):
    """
    Take an AI generated description of a skill adhering to the TOML format and ensures it is valid.
    """
    required_parameters = [
        "skill_name",
        "skill_description",
        "output_name",
        "output_description",
        "output_uses",
        "output_type",
        "arguments"
    ]

    arguments_required_parameters = [
        "argument_name",
        "argument_identifier",
        "argument_description",
        "argument_sources",
        "argument_type"
    ]

    try:
        parsed_toml = toml.loads(description_toml)
        description = parsed_toml.get("description", {})
        arguments = description.get("arguments", [])

        for argument in arguments:
            for param in arguments_required_parameters:
                if param not in argument:
                    return False, param

        for param in required_parameters:
            if param not in description and param not in arguments:
                return False, param

        return True, None

    except toml.TomlDecodeError:
        return False, "TOMLDecodeError"

def simplified_yaml(yaml_file):
    if isinstance(yaml_file, dict):
        for key, value in yaml_file.items():
            if isinstance(value, dict):
                simplified_yaml(value)
            elif isinstance(value, list):
                for item in value:
                    simplified_yaml(item)
            elif isinstance(value, PreservedScalarString):
                yaml_file[key] = value.strip()

    elif isinstance(yaml_file, list):
        for item in yaml_file:
            simplified_yaml(item)

    text = yaml.dump(yaml_file, Dumper=yaml.RoundTripDumper, default_flow_style=False, indent=1, block_seq_indent=1, width=999999, allow_unicode=True)
    text = re.sub(r'  ', r' ', text)
    text = text.replace('|-', '')
    text = text.replace('|', '')
    text = text.strip()
    return text

def get_skprompt_template(template_parent_directory, is_yaml=False):
    """
    Get the skprompt.txt file from the folder and return it as a string.
    """
    prompt_file = "skprompt.txt"
    if is_yaml:
        prompt_file = "skprompt.yaml"
    
    file_location = template_parent_directory + "/" + prompt_file
    with open(file_location, 'r') as f:
        return f.read()

def get_skill_name_from_directory(directory):
    """
    Get the skill name from the directory.
    Counting from the end, find the folder that says "Skills" and then add all the folders after that.
    This is the skill name.
    """
    directory_parts = os.path.normpath(directory).split(os.sep)
    for i, part in enumerate(directory_parts):
        if part == "Skills":
            directory_parts = directory_parts[i+1:]
            break
    
    name = ""
    for part in directory_parts:
        name += f"{part}."
    name = name[:-1]

    return name

def get_full_prompt(template, describing_skill_location):
    """Get the full prompt from the template."""
    describing_skill = get_skprompt_template(describing_skill_location, is_yaml=True)
    embdedded_template_param = "{{$undescribed_template}}"
    full_prompt = describing_skill.replace(embdedded_template_param, template)
    return full_prompt

def get_injected_template(directory, describe_template_location):
    """Get the description template with the skill template injected."""
    #Get the skill we are describing.
    template = get_skprompt_template(directory)
    full_prompt = get_full_prompt(template, describe_template_location)
    #Simplify the YAML
    full_prompt = simplified_yaml(full_prompt)
    return full_prompt

def load_openai():
    """Load the OpenAI API key."""
    env_vars = dotenv_values(".env")
    openai.api_key = env_vars["OPENAI_API_KEY"]
    return env_vars

def clean_description(description):
    """ Clean the description of extra newlines and spaces. """
    description = description.replace("\n\n", "\n")
    description.strip()
    return description

def save_description(directory, description):
    """Save the description to a TOML file."""
    description = clean_description(description)
    skill_name = get_skill_name_from_directory(directory)
    skill_description = toml.loads(description)
    skill_description["description"]["skill_name"] = skill_name
    description = toml.dumps(skill_description)
    file_location = directory + "/description.toml"
    with open(file_location, 'w') as f:
        f.write(description)

def main(directory, describe_template):
    """Generate a description for the skill."""
    openai_settings = load_openai()
    prompt = get_injected_template(directory, describe_template)
    response = openai.Completion.create(
            model=openai_settings["OPENAI_MODEL"],
            prompt=prompt,
            max_tokens=2000,
            temperature=0.1 )
    
    description = response.choices[0].text
    validation_results = validate_description_generation(description)
    if validation_results[0]:
        save_description(directory, description)
    else:
        print("Description generation failed validation.", validation_results[1])
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a description file for skills in the repo.')
    parser.add_argument('skill_template_location', type=str, help='The directory where the skill that needs describing is stored.')
    parser.add_argument('describe_template_location', type=str, help='The location of the describe template.')
    parser.add_argument('--debug', type=bool, help='Debug mode to make sure validator is working', default=False)
    parser.add_argument('--auto_search', type=bool, help='Tags the skill template location as a parent with many children. Describes each child.', default=False)
    args = parser.parse_args()

    directory = args.skill_template_location
    describe_template_location = args.describe_template_location
    debug = args.debug
    auto_search = args.auto_search

    if debug:
        # Example usage
        description_toml_string = """
        [description]
        skill_name = "Image Recognition"
        skill_description = "The ability to identify objects and patterns in images."
        output_name = "recognized_objects"
        output_description = "The recognized objects in the image."
        output_uses = "To provide object detection and classification in image processing."
        output_type = "json"

        [[description.arguments]]
        argument_name = "image_url"
        argument_identifier = "{{image_url}}"
        argument_description = "The URL or path to the image for recognition."
        argument_sources = "User input or external API."
        argument_type = "string"
        """
        results = validate_description_generation(description_toml_string)

        if results[0]:
            print("All required parameters exist in the TOML string.")
        else:
            print("One or more required parameters are missing in the TOML string.", results[1])
    elif auto_search:
        directory = os.path.normpath(directory)
        for root, dirs, files in os.walk(directory):
            for dir in dirs:
                child_path = os.path.join(root, dir)
                main(child_path, describe_template_location)
    else:
        main(directory, describe_template_location)
