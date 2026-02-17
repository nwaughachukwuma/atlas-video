The code here contains the core components and logic of atlas, the multimodal insights engine used at VeedoAI. We want to open-source atlas by converting it into a CLI application which anyone can use. The immediate goal is to strip all the logic for writing to Elasticsearch, including logic for writing to cloud task. In place, we'll use a local vector store (let's use zvec, see docs below) for a fast, local vector search workflow. Here's a typical example

1. the user has a local video they want to derive multimodal understanding for
2. they point atlas to the video, like so: atlas index video.mp4 --chunk-duration=15s --overlap=1s
3. they could also just extract multimodal transcripts in one shot without indexing, like so: atlas extract video.mp4 --chunk-duration=15s --overlap=1s
4. when extracting, we won't use the zvec. we'll only use zvec when indexing
5. the user is expected to provide their own gemini api key as GEMINI_API_KEY

Much of the core logic can be kept and reuse if useful. Remove any redundant or replace poorly performant logic.

Make this repo a complete pypi-ready library, so add pyproject and other setup files to make it publishable and installable from pypi. the goal is for anyone to install and use it on their terminal for multimodal video understanding.

Don't make mistakes.
