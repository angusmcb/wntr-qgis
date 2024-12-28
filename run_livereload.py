from livereload import Server, shell

COMMAND = "make html"

if __name__ == "__main__":
    server = Server()
    server.watch("*.rst", shell(COMMAND, cwd="docs"), delay=1)
    server.watch("*.md", shell(COMMAND, cwd="docs"), delay=1)
    server.watch("*.py", shell(COMMAND, cwd="docs"), delay=1)
    server.watch("docs/_static/*", shell(COMMAND, cwd="docs"), delay=1)
    server.watch("docs/_templates/*", shell(COMMAND, cwd="docs"), delay=1)
    server.serve(root="docs/_build/html")
