# resourceclassupdater
A bulk updater for CircleCI, designed to update all macos resources towards Gen 2/M1.

## Usage

1. Install the required Python packages with `pip install -r requirements.txt`
2. Run with at least one of these flags:
  * G1-G2 - Convert all Gen 1 macos to Gen 2 Medium.
  * G1-G2M1 - Convert all Gen 1 macos medium to Gen 2 Medium, and Gen 1 Large to M1 Large.
  * G1-M1 - Convert all Gen 1 macos to M1
  * G2-M1 - Convert all Gen 2 macos to M1
  * Example: `py ./main.py g1-g2 g2-m1`
4. Either edit the main.py file to insert your API Key and Organization name, or input them when prompted.

When the script has run, branches shuold have been created with the name `MacosResourceAutomaticUpdate` (unless edited) and a Pull Request created as well. Also, during this, local copies of the config.yml files will be created. These can safely be deleted, but you may want to check them out for debugging purposes.

If the script fails due to a branch creation error, ensure the branch does not exist already. If you ran the script once, it already exists, and thus needs to be deleted.
