import os

folder = os.path.dirname(os.path.abspath(__file__))

for filename in os.listdir(folder):
    if filename.endswith(".txt"):
        filepath = os.path.join(folder, filename)

        with open(filepath, "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            parts = line.strip().split()

            if len(parts) > 0 and parts[0] == "1":
                parts[0] = "0"

            new_lines.append(" ".join(parts) + "\n")

        with open(filepath, "w") as f:
            f.writelines(new_lines)

print("Done")
