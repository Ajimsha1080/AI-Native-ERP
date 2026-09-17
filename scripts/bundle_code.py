import os

exclude_dirs = {'.git', '.pytest_cache', '__pycache__', 'node_modules', '.next', 'data', 'dist', 'build'}
exclude_exts = {'.pyc', '.ico', '.svg', '.png', '.jpg', '.lock', '.db', '.zip'}

output_file = 'codebase_bundle.txt'
count = 0

with open(output_file, 'w', encoding='utf-8') as outfile:
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in sorted(files):
            ext = os.path.splitext(f)[1]
            if ext in exclude_exts or f in [output_file, 'package-lock.json', 'bundle_code.py']:
                continue
            path = os.path.join(root, f)
            rel_path = os.path.relpath(path, '.').replace('\\', '/')
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as infile:
                    content = infile.read()
                    outfile.write(f"================================================\n")
                    outfile.write(f"FILE: {rel_path}\n")
                    outfile.write(f"================================================\n")
                    outfile.write(content + "\n\n")
                    count += 1
            except Exception as e:
                pass

print(f"Successfully bundled {count} files into {output_file}")
