import sys
import yaml
import json

def parse(yamlfile):
    with open(yamlfile) as file:
        # The FullLoader parameter handles the conversion from YAML
        # scalar values to Python the dictionary format
        array = yaml.load(file, Loader=yaml.FullLoader)

        array=str(array).replace("'", '"')
        data  = json.loads(array)
        print (data['required'])

if __name__ == "__main__":
    parse(sys.argv[1])

