# About

These scripts should ensure that all book versions referenced by the ABL are present in the CORGI database

# Dependencies

- bash
- docker
- curl
- jq
- ssh

# How to run

- First run the abl_migration with `run_abl_migration` (ensures all required information is present in the database)
- You must export the following environment variables
    - `GITHUB_TOKEN` (token with minimum of repo scope)
    - `ABL_RAW_URL` (Raw GitHub URL for ABL to migrate from)
    - `CORGI_URL` (Base URL, without trailing slash, of the CORGI instance to migrate ABL to; example: https://corgi-staging.ce.openstax.org)
    - `HOST` (The ssh host that the container is running on; this should be a uri of the form ssh://)
    - `CONTAINER` (the id of the container you want to run the migration on)
- run with `./run_abl_migration.bash`
- Second, run `gh_abl_to_corgi_abl.bash` (transforms github ABL to CORGI format and sends a POST request to update the ABL)

