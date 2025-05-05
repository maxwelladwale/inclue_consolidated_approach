import os
import xml.etree.ElementTree as ET

def check_xml_files(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.xml'):
                filepath = os.path.join(root, file)
                try:
                    tree = ET.parse(filepath)
                    root_elem = tree.getroot()
                    if root_elem.tag != 'odoo':
                        print(f"ERROR in {filepath}: Root element is not 'odoo'")
                    data_elements = root_elem.findall('data')
                    if len(data_elements) != 1:
                        print(f"ERROR in {filepath}: Found {len(data_elements)} data elements, expected 1")
                    print(f"OK: {filepath}")
                except ET.ParseError as e:
                    print(f"ERROR parsing {filepath}: {e}")

check_xml_files('.')