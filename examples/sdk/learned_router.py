"""Opt into the bundled experimental Python learned router."""

from nestra import FileProjectStore, NestraRuntime, load_bundled_router_model

nestra = NestraRuntime(
    store=FileProjectStore(".nestra/learned-demo"),
    router_model=load_bundled_router_model(),
)
nestra.ingest(
    project_id="casting",
    documents=[
        {
            "title": "Bobbi Bacha",
            "text": "Bobbi Bacha was portrayed by actress Sissy Spacek.",
            "trust": "trusted",
        },
        {
            "title": "Sissy Spacek",
            "text": "Mary Elizabeth Spacek is known as Sissy Spacek.",
            "trust": "trusted",
        },
    ],
)
plan = nestra.plan(project_id="casting", question="What is Sissy Spacek's middle name?")
print(
    {"route": plan["route"], "providerRequired": plan["providerRequired"], "router": plan["router"]}
)
