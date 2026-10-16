from src.modules.tools.resource.service import ResourceService

service = ResourceService()

print(
    service.open_file(
        # r"C:\Windows\System32\drivers\etc\hosts"
        r"D:\movie\Wistoria Wand and Sword-S01-1080p-[HIN-ENG-JAP]-Vegamovies.is\Wistoria Wand and Sword-S01-1080p-[HIN-ENG-JAP]-Vegamovies.is"
    )
)
