import requests
import json
import sys
import base64
from ruamel.yaml import YAML
from pathlib import Path

#Configuration
api_org = "" #The organization you'll be scanning.
api_key="" #Personal Access Token
new_branch_name="MacosResourceAutomaticUpdate" #Make sure this is unique.

#check for initial flags.

for s in sys.argv:
    s=s.lower()

convert_gen1_to_gen2 = "g1-g2" in sys.argv
convert_gen1_to_gen2_m1_large = "g1-g2m1" in sys.argv
convert_gen1_to_m1 = "g1-m1" in sys.argv
convert_gen2_to_m1 = "g2-m1" in sys.argv

if convert_gen1_to_gen2 == True and convert_gen1_to_m1 == True:
    print ("Conflict - gen1 marked to migrate to both m1 and gen2")
    sys.exit(1)

if convert_gen1_to_m1 == False and convert_gen1_to_gen2 == False and convert_gen2_to_m1 == False and convert_gen1_to_gen2_m1_large == False:
    print ("Please add at least one of the following parameters:")
    print ("G1-G2 - Convert all Gen 1 macos to Gen 2 Medium.")
    print ("G1-G2M1 - Convert all Gen 1 macos medium to Gen 2 Medium, and Gen 1 Large to M1 Large.")
    print ("G1-M1 - Convert all Gen 1 macos to M1")
    print ("G2-M1 - Convert all Gen 2 macos to M1")
    sys.exit(1)

#If any of the configuration elements up top are not filled in, ask for them here.
while api_org == "":
    api_org = input("Organization you wish to scan for repos:")

while api_key == "":
    api_key = input("Personal Access Token:")

while new_branch_name == "":
    new_branch_name = input("New branch name. Ensure it is unique:")

#Relevant but unlikely to change definitions here.
api_url = "https://api.github.com/"
headers =  {"Content-Type":"application/json", "Authorization":"Bearer " + api_key}

yaml = YAML()

#Get all repos.
def fetch_repos():
    call_url = api_url+"orgs/"+api_org+"/repos"
    res = requests.get(call_url, headers=headers)
    if res.status_code != 200:
        print("Organization " + api_org + " is not valid, or you don't have access to it. Confirm your API Key is correct as well.")
        sys.exit(1)
    return res

#For each repo, investigate for a .circleci/config.yml file being present in the main branch.
def repo_scan(repo):
    call_url = api_url + "repos/" + api_org + "/" + repo["name"] + "/contents/.circleci/config.yml"

    result = requests.get(call_url, headers=headers)


    if result.status_code == 200:
        data = json.loads(result.content)
        yaml_file = requests.get(data["download_url"], headers=headers)
        
        if str(yaml_file.content).find("macos:") == -1:
            print("No entry for \"macos:\" found")
            return False
        
        else:
            return_data = dict()
            return_data['content'] = str(yaml_file.content)
            return_data['sha'] = data["sha"]
            return return_data
    
    else:
        print("No .circleci/config.yml file found.")
        return False

#Determine if there are any macos entries at all.
def macos_check(config: str):
    if config.find("macos:") > -1:
        return True
    return False
    
#An initial call to get all repos.
response = fetch_repos()
repos = response.json()

#Run through each of them.
for r in repos:
    print("\n\n====== Working on Repo: " + r["name"] + " ======")
    result = repo_scan(r)
    if result == False: #Any error, we leave.
        continue

    result_text = result['content']

    #Split into different variables per newline, and remove leading dashes if they are present.
    result_text = result_text.replace(r"---", "")
    result_text = result_text.replace(r'\n', '\n')
    result_text = result_text[2:-1]

    result_yaml = yaml.load(result_text)
    change_made=False #If no changes are made, we can quit after this is done.

    print("\n=== Updating macos resource classes ===")

    for attr, value in result_yaml['jobs'].items():
        if "macos" in value:

            ## The resource class can be present under macos, or on the same depth tas it, so we need to account for both.
            ## We first check for the same depth, then, we check under macos.
            depth = 0
            if "resource_class" in value:
                old_resource = value["resource_class"]
            elif "resource_class" in value["macos"]:
                depth = 1
                old_resource = value["macos"]["resource_class"]
            else:
                print("Unexpected lack of resource_class tag.")
                continue
            resource = ""
            match old_resource:
                #Updates depending on the flag used.
                case "medium":
                    if convert_gen1_to_m1 == True:
                        resource = "macos.m1.medium.gen1"
                    elif convert_gen1_to_gen2 == True or convert_gen1_to_gen2_m1_large == True:
                        resource = "macos.x86.medium.gen2"
                case "large":
                    if convert_gen1_to_m1 == True or convert_gen1_to_gen2_m1_large == True:
                        resource = "macos.m1.large.gen1"
                    elif convert_gen1_to_gen2 == True:
                        resource = "macos.x86.medium.gen2"
                case "macos.x86.medium.gen2":
                    if convert_gen2_to_m1 == True:
                        resource = "macos.m1.medium.gen1"
            
            #If the resource variable matches the Resource we started with, no change was made - otherwise, one was made.
            if (resource != old_resource and resource != ""):
                change_made=True
                if depth == 0:
                    value["resource_class"] = resource
                elif depth == 1:
                    value["macos"]["resource_class"] = resource
                
                print("Updating from " + old_resource + " to " + resource)
        else:
            continue
    
    if change_made == False:
        print("No changes triggered, moving to next repo.")
        continue
    
    print("\n=== Writing file locally ===")
    #We save the file locally so that a copy is available to view, and so that it's easier to json-ify later.
    with open(r['name'] + ".yml", "w") as file:
        yaml.dump(result_yaml, file)
        print("Output for updated config saved in file: " + r['name'] + ".yml")

    #Prepare URLs for API Calls. Very repetitive, but hey.
    base_repo_url = api_url + "repos/" + api_org + "/" + r["name"]
    ref_head_url = base_repo_url + "/git/refs/heads"
    create_branch_url = base_repo_url + "/git/refs"
    update_url = base_repo_url + "/contents/.circleci/config.yml"
    create_pr_url = base_repo_url + "/pulls"

    #Attempt to create a branch. If it already exists, we will assume the script has already been run and move on.
    print("\n=== Creating Branch ===")
    branches = requests.get(ref_head_url, headers=headers).json()
    branch, sha = branches[-1]['ref'], branches[-1]['object']['sha']

    branch_create_res = requests.post(create_branch_url, headers=headers, data=json.dumps({
        "ref": "refs/heads/" + new_branch_name,
        "sha": sha
    }))
    if branch_create_res.status_code != 201 and branch_create_res.status_code != 200:
        print("Error when attempting to create branch: ", branch_create_res.status_code)
        print("Branch " + new_branch_name + " probably already exists, did you run the script before? If so, please delete the old branch.")
        continue

    print("Branch created.")
    print("\n=== Updating Config ===")

    #Open the file created above and encode it.
    file_content = Path(r['name']+".yml").read_text()
    file_content = file_content.replace('\n',"\n")
    file_content = str.encode(file_content)
    put_data = {
        "message": "Automatic resource class update for macos. gen1 and/or 2 to gen2 or m1",
        "content": base64.b64encode(file_content).decode("utf-8"), 
        "sha": result['sha'],
        "branch": new_branch_name
    }

    put_result = requests.put(update_url, headers=headers, data=json.dumps(put_data))
    
    if put_result.status_code != 201 and put_result.status_code != 200:
        print("Error when attempting to update config.yml:", put_result.status_code)
        continue

    print("Config updated.") 
    
    #Successful commit to the branch, now we move on to a PR.
    print("\n=== Creating Pull Request ===")

    pr_data = {
        "title": "Update macos resource classes",
        "head": new_branch_name,
        "base": r["default_branch"],
        "body": "This PR is opened by a script, designed to help bulk update macos resource classes."
    }

    pr_result = requests.post(create_pr_url, headers=headers, data=json.dumps(pr_data))

    if pr_result.status_code != 201:
        print("Error creating pull request: ", pr_result.status_code)
        continue
    print("\n\n========================================")
    print("=========*      Success!      *=========")
    print("========================================")
    print("Pull request opened, URL: " + pr_result.json()["html_url"])
