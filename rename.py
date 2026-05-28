import os

folder = os.path.dirname(os.path.abspath(__file__))

for filename in os.listdir(folder):
    if not filename.startswith("dataset1_"):
        old_path = os.path.join(folder, filename)

        new_name = "dataset1_" + filename
        new_path = os.path.join(folder, new_name)

        if not os.path.exists(new_path):
            os.rename(old_path, new_path)

print("Done")