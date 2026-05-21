"""Deploy Producer Agent (with sub-agents and skills) to Agent Engine."""

import os

import vertexai
from vertexai import agent_engines

from agents.producer import producer_agent


def main():
    vertexai.init(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_REGION", "us-central1"),
        staging_bucket=f"gs://{os.environ['GOOGLE_CLOUD_PROJECT']}-staging",
    )

    print("Deploying Producer Agent...")

    remote_agent = agent_engines.create(
        producer_agent,
        requirements=[
            "google-cloud-aiplatform[agent_engines,adk]>=1.114.0",
            "google-adk>=1.25.0",
            "google-cloud-speech>=2.25.0",
            "google-cloud-storage>=2.18.0",
            "voyageai>=0.3.0",
            "requests>=2.32.0",
        ],
        extra_packages=["./skills"],
        display_name="Pocket Producer",
        description="Agentic memory for music creation",
        env_vars={
            "MCP_SERVER_URL": os.environ["MCP_SERVER_URL"],
            "AUDIO_SERVICE_URL": os.environ.get("AUDIO_SERVICE_URL", ""),
            "VOYAGE_API_KEY": os.environ["VOYAGE_API_KEY"],
            "GCS_BUCKET": os.environ["GCS_BUCKET"],
        },
    )

    print(f"\nDeployed: {remote_agent.resource_name}")
    print(f"\nAdd to .env:\nPRODUCER_RESOURCE_NAME={remote_agent.resource_name}")


if __name__ == "__main__":
    main()
