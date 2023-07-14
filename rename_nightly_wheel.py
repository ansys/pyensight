import datetime
import glob
import os

# rename: ansys_pyensight_core-0.2.dev0-py3-none-any.whl to
# ansys_pyensight_core-0.2.dev0-{date_tag}-py3-none-any.whl
# monotonically increasing number with minute level
# resolution so a nightly can be run once a minute
date_tag = datetime.datetime.now().strftime("%Y%m%d%H%M")
for name in glob.glob("dist/*.whl"):
    chunks = name.split("-")
    if len(chunks) == 5:
        chunks.insert(2, date_tag)
        new_name = "-".join(chunks)
        os.rename(name, new_name)
        print(f"Rename wheel to: '{new_name}'")
