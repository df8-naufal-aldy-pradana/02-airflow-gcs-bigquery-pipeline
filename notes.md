1. How to set project 
```
gcloud config set project $MY_PROJECT_ID
```
2. How to list project 
```
gcloud projects list
```
3. If gcloud: command not found
```
source ~/google-cloud-sdk/path.bash.inc
source ~/google-cloud-sdk/completion.bash.inc
```

gcloud iam service-accounts create fellowship7-sa \
    --description="This service account is for data-fellowship7" \
    --display-name="fellowship7-sa"


