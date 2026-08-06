"""Zero-token retrieval example."""

from nestra import FileProjectStore, NestraRuntime

nestra = NestraRuntime(store=FileProjectStore(".nestra"))
nestra.ingest(
    project_id="apollo",
    documents=[
        {
            "title": "Apollo 11",
            "text": "Apollo 11 landed on the Moon in July 1969.",
            "trust": "trusted",
            "sourceUri": "https://www.nasa.gov/mission/apollo-11/",
        }
    ],
)
result = nestra.query(
    project_id="apollo", question="Show the evidence sources for Apollo 11", mode="retrieval"
)
print(result["telemetry"]["usage"]["totalTokens"])  # 0
