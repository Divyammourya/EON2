from src.modules.tools.resource.launcher import ResourceLauncher

launcher = ResourceLauncher()

tests = [
    "chrome",
    "downloads",
    "github",
    "somethingrandom",
]

for query in tests:

    print("-" * 40)

    result = launcher.open(query)

    print(query)

    print(result)
