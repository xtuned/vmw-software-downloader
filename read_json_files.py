import os
import json

root_dir = '/zPod/zPodLibrary/official'
json_files = []

for subdir, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith('.json'):
            json_files.append(os.path.join(subdir, file))

json_contents = []
for json_file in json_files:
    with open(json_file) as f:
        json_contents.append(json.load(f))

print(json_contents)