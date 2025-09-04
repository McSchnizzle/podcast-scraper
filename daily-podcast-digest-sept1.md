daily-podcast-digest
succeeded 5 minutes ago in 5m 47s
Search logs
3s
Current runner version: '2.328.0'
Runner Image Provisioner
Operating System
Runner Image
GITHUB_TOKEN Permissions
Secret source: Actions
Prepare workflow directory
Prepare all required actions
Getting action download info
Download action repository 'actions/checkout@v4' (SHA:08eba0b27e820071cde6df949e0beb9ba4906955)
Download action repository 'actions/setup-python@v5' (SHA:a26af69be951a213d495a4c3e4e4022e16d87065)
Download action repository 'actions/cache@v4' (SHA:0400d5f644dc74513175e3cd8d07132dd4860809)
Download action repository 'awalsh128/cache-apt-pkgs-action@latest' (SHA:2c09a5e66da6c8016428a2172bd76e5e4f14bb17)
Download action repository 'actions/upload-artifact@v4' (SHA:ea165f8d65b6e75b540449e92b4886f43607fa02)
Download action repository 'softprops/action-gh-release@v1' (SHA:de2c0eb89ae2a093876385947365aca7b0e5f844)
Getting action download info
Complete job name: daily-podcast-digest
5s
Run actions/checkout@v4
Syncing repository: McSchnizzle/podcast-scraper
Getting Git version info
Temporarily overriding HOME='/home/runner/work/_temp/6c6fb06f-4916-41c4-a2b0-e40a5d6e4b49' before making global git config changes
Adding repository directory to the temporary git global config as a safe directory
/usr/bin/git config --global --add safe.directory /home/runner/work/podcast-scraper/podcast-scraper
Deleting the contents of '/home/runner/work/podcast-scraper/podcast-scraper'
Initializing the repository
Disabling automatic garbage collection
Setting up auth
Fetching the repository
Determining the checkout info
/usr/bin/git sparse-checkout disable
/usr/bin/git config --local --unset-all extensions.worktreeConfig
Checking out the ref
/usr/bin/git log -1 --format=%H
62f737156a98a50c29f41ad9126d39dc1c245685
0s
Run actions/setup-python@v5
Installed versions
3s
Run actions/cache@v4
Cache hit for: Linux-pip-57d5218f0d241cadb5c122e6101f3e19941e64965e863ead5a30525509c59da5-v1
Received 12582912 of 138688278 (9.1%), 12.0 MBs/sec
Received 134493974 of 138688278 (97.0%), 64.1 MBs/sec
Received 138688278 of 138688278 (100.0%), 62.5 MBs/sec
Cache Size: ~132 MB (138688278 B)
/usr/bin/tar -xf /home/runner/work/_temp/18dc1e6b-7fd9-41b2-88c5-6c2a129d3d53/cache.tzst -P -C /home/runner/work/podcast-scraper/podcast-scraper --use-compress-program unzstd
Cache restored successfully
Cache restored from key: Linux-pip-57d5218f0d241cadb5c122e6101f3e19941e64965e863ead5a30525509c59da5-v1
19s
Run python -m pip install --upgrade pip
Requirement already satisfied: pip in /opt/hostedtoolcache/Python/3.11.13/x64/lib/python3.11/site-packages (25.2)
Collecting requests>=2.32.0 (from -r requirements.txt (line 1))
  Using cached requests-2.32.5-py3-none-any.whl.metadata (4.9 kB)
Collecting feedparser>=6.0.0 (from -r requirements.txt (line 2))
  Using cached feedparser-6.0.11-py3-none-any.whl.metadata (2.4 kB)
Collecting youtube-transcript-api>=0.6.0 (from -r requirements.txt (line 3))
  Using cached youtube_transcript_api-1.2.2-py3-none-any.whl.metadata (24 kB)
Collecting python-dotenv>=1.0.0 (from -r requirements.txt (line 4))
  Using cached python_dotenv-1.1.1-py3-none-any.whl.metadata (24 kB)
Collecting anthropic>=0.20.0 (from -r requirements.txt (line 5))
  Using cached anthropic-0.64.0-py3-none-any.whl.metadata (27 kB)
Collecting beautifulsoup4>=4.12.0 (from -r requirements.txt (line 6))
  Using cached beautifulsoup4-4.13.5-py3-none-any.whl.metadata (3.8 kB)
Collecting python-dateutil>=2.8.0 (from -r requirements.txt (line 7))
  Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
Collecting numpy>=1.24.0 (from -r requirements.txt (line 8))
  Using cached numpy-2.3.2-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl.metadata (62 kB)
Collecting faster-whisper>=1.0.0 (from -r requirements.txt (line 9))
  Using cached faster_whisper-1.2.0-py3-none-any.whl.metadata (16 kB)
Collecting openai>=1.0.0 (from -r requirements.txt (line 10))
  Using cached openai-1.102.0-py3-none-any.whl.metadata (29 kB)
Collecting charset_normalizer<4,>=2 (from requests>=2.32.0->-r requirements.txt (line 1))
  Using cached charset_normalizer-3.4.3-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (36 kB)
Collecting idna<4,>=2.5 (from requests>=2.32.0->-r requirements.txt (line 1))
  Using cached idna-3.10-py3-none-any.whl.metadata (10 kB)
Collecting urllib3<3,>=1.21.1 (from requests>=2.32.0->-r requirements.txt (line 1))
  Using cached urllib3-2.5.0-py3-none-any.whl.metadata (6.5 kB)
Collecting certifi>=2017.4.17 (from requests>=2.32.0->-r requirements.txt (line 1))
  Using cached certifi-2025.8.3-py3-none-any.whl.metadata (2.4 kB)
Collecting sgmllib3k (from feedparser>=6.0.0->-r requirements.txt (line 2))
  Using cached sgmllib3k-1.0.0-py3-none-any.whl
Collecting defusedxml<0.8.0,>=0.7.1 (from youtube-transcript-api>=0.6.0->-r requirements.txt (line 3))
  Using cached defusedxml-0.7.1-py2.py3-none-any.whl.metadata (32 kB)
Collecting anyio<5,>=3.5.0 (from anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached anyio-4.10.0-py3-none-any.whl.metadata (4.0 kB)
Collecting distro<2,>=1.7.0 (from anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached distro-1.9.0-py3-none-any.whl.metadata (6.8 kB)
Collecting httpx<1,>=0.25.0 (from anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached httpx-0.28.1-py3-none-any.whl.metadata (7.1 kB)
Collecting jiter<1,>=0.4.0 (from anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached jiter-0.10.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (5.2 kB)
Collecting pydantic<3,>=1.9.0 (from anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached pydantic-2.11.7-py3-none-any.whl.metadata (67 kB)
Collecting sniffio (from anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
Collecting typing-extensions<5,>=4.10 (from anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached typing_extensions-4.15.0-py3-none-any.whl.metadata (3.3 kB)
Collecting httpcore==1.* (from httpx<1,>=0.25.0->anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached httpcore-1.0.9-py3-none-any.whl.metadata (21 kB)
Collecting h11>=0.16 (from httpcore==1.*->httpx<1,>=0.25.0->anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
Collecting annotated-types>=0.6.0 (from pydantic<3,>=1.9.0->anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached annotated_types-0.7.0-py3-none-any.whl.metadata (15 kB)
Collecting pydantic-core==2.33.2 (from pydantic<3,>=1.9.0->anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached pydantic_core-2.33.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.8 kB)
Collecting typing-inspection>=0.4.0 (from pydantic<3,>=1.9.0->anthropic>=0.20.0->-r requirements.txt (line 5))
  Using cached typing_inspection-0.4.1-py3-none-any.whl.metadata (2.6 kB)
Collecting soupsieve>1.2 (from beautifulsoup4>=4.12.0->-r requirements.txt (line 6))
  Using cached soupsieve-2.8-py3-none-any.whl.metadata (4.6 kB)
Collecting six>=1.5 (from python-dateutil>=2.8.0->-r requirements.txt (line 7))
  Using cached six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
Collecting ctranslate2<5,>=4.0 (from faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached ctranslate2-4.6.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (10 kB)
Collecting huggingface-hub>=0.13 (from faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached huggingface_hub-0.34.4-py3-none-any.whl.metadata (14 kB)
Collecting tokenizers<1,>=0.13 (from faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached tokenizers-0.22.0-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.8 kB)
Collecting onnxruntime<2,>=1.14 (from faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached onnxruntime-1.22.1-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl.metadata (4.6 kB)
Collecting av>=11 (from faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached av-15.1.0-cp311-cp311-manylinux_2_28_x86_64.whl.metadata (4.6 kB)
Collecting tqdm (from faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached tqdm-4.67.1-py3-none-any.whl.metadata (57 kB)
Requirement already satisfied: setuptools in /opt/hostedtoolcache/Python/3.11.13/x64/lib/python3.11/site-packages (from ctranslate2<5,>=4.0->faster-whisper>=1.0.0->-r requirements.txt (line 9)) (65.5.0)
Collecting pyyaml<7,>=5.3 (from ctranslate2<5,>=4.0->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached PyYAML-6.0.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (2.1 kB)
Collecting coloredlogs (from onnxruntime<2,>=1.14->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached coloredlogs-15.0.1-py2.py3-none-any.whl.metadata (12 kB)
Collecting flatbuffers (from onnxruntime<2,>=1.14->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached flatbuffers-25.2.10-py2.py3-none-any.whl.metadata (875 bytes)
Collecting packaging (from onnxruntime<2,>=1.14->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached packaging-25.0-py3-none-any.whl.metadata (3.3 kB)
Collecting protobuf (from onnxruntime<2,>=1.14->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached protobuf-6.32.0-cp39-abi3-manylinux2014_x86_64.whl.metadata (593 bytes)
Collecting sympy (from onnxruntime<2,>=1.14->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached sympy-1.14.0-py3-none-any.whl.metadata (12 kB)
Collecting filelock (from huggingface-hub>=0.13->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached filelock-3.19.1-py3-none-any.whl.metadata (2.1 kB)
Collecting fsspec>=2023.5.0 (from huggingface-hub>=0.13->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached fsspec-2025.7.0-py3-none-any.whl.metadata (12 kB)
Collecting hf-xet<2.0.0,>=1.1.3 (from huggingface-hub>=0.13->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached hf_xet-1.1.9-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (4.7 kB)
Collecting humanfriendly>=9.1 (from coloredlogs->onnxruntime<2,>=1.14->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached humanfriendly-10.0-py2.py3-none-any.whl.metadata (9.2 kB)
Collecting mpmath<1.4,>=1.1.0 (from sympy->onnxruntime<2,>=1.14->faster-whisper>=1.0.0->-r requirements.txt (line 9))
  Using cached mpmath-1.3.0-py3-none-any.whl.metadata (8.6 kB)
Using cached requests-2.32.5-py3-none-any.whl (64 kB)
Using cached charset_normalizer-3.4.3-cp311-cp311-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (150 kB)
Using cached idna-3.10-py3-none-any.whl (70 kB)
Using cached urllib3-2.5.0-py3-none-any.whl (129 kB)
Using cached feedparser-6.0.11-py3-none-any.whl (81 kB)
Using cached youtube_transcript_api-1.2.2-py3-none-any.whl (485 kB)
Using cached defusedxml-0.7.1-py2.py3-none-any.whl (25 kB)
Using cached python_dotenv-1.1.1-py3-none-any.whl (20 kB)
Using cached anthropic-0.64.0-py3-none-any.whl (297 kB)
Using cached anyio-4.10.0-py3-none-any.whl (107 kB)
Using cached distro-1.9.0-py3-none-any.whl (20 kB)
Using cached httpx-0.28.1-py3-none-any.whl (73 kB)
Using cached httpcore-1.0.9-py3-none-any.whl (78 kB)
Using cached jiter-0.10.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (352 kB)
Using cached pydantic-2.11.7-py3-none-any.whl (444 kB)
Using cached pydantic_core-2.33.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (2.0 MB)
Using cached typing_extensions-4.15.0-py3-none-any.whl (44 kB)
Using cached beautifulsoup4-4.13.5-py3-none-any.whl (105 kB)
Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
Using cached numpy-2.3.2-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (16.9 MB)
Using cached faster_whisper-1.2.0-py3-none-any.whl (1.1 MB)
Using cached ctranslate2-4.6.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (38.6 MB)
Using cached onnxruntime-1.22.1-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (16.5 MB)
Using cached PyYAML-6.0.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (762 kB)
Using cached tokenizers-0.22.0-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (3.3 MB)
Using cached huggingface_hub-0.34.4-py3-none-any.whl (561 kB)
Using cached hf_xet-1.1.9-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (3.2 MB)
Using cached openai-1.102.0-py3-none-any.whl (812 kB)
Using cached annotated_types-0.7.0-py3-none-any.whl (13 kB)
Using cached av-15.1.0-cp311-cp311-manylinux_2_28_x86_64.whl (39.6 MB)
Using cached certifi-2025.8.3-py3-none-any.whl (161 kB)
Using cached fsspec-2025.7.0-py3-none-any.whl (199 kB)
Using cached h11-0.16.0-py3-none-any.whl (37 kB)
Using cached packaging-25.0-py3-none-any.whl (66 kB)
Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
Using cached sniffio-1.3.1-py3-none-any.whl (10 kB)
Using cached soupsieve-2.8-py3-none-any.whl (36 kB)
Using cached tqdm-4.67.1-py3-none-any.whl (78 kB)
Using cached typing_inspection-0.4.1-py3-none-any.whl (14 kB)
Using cached coloredlogs-15.0.1-py2.py3-none-any.whl (46 kB)
Using cached humanfriendly-10.0-py2.py3-none-any.whl (86 kB)
Using cached filelock-3.19.1-py3-none-any.whl (15 kB)
Using cached flatbuffers-25.2.10-py2.py3-none-any.whl (30 kB)
Using cached protobuf-6.32.0-cp39-abi3-manylinux2014_x86_64.whl (322 kB)
Using cached sympy-1.14.0-py3-none-any.whl (6.3 MB)
Using cached mpmath-1.3.0-py3-none-any.whl (536 kB)
Installing collected packages: sgmllib3k, mpmath, flatbuffers, urllib3, typing-extensions, tqdm, sympy, soupsieve, sniffio, six, pyyaml, python-dotenv, protobuf, packaging, numpy, jiter, idna, humanfriendly, hf-xet, h11, fsspec, filelock, feedparser, distro, defusedxml, charset_normalizer, certifi, av, annotated-types, typing-inspection, requests, python-dateutil, pydantic-core, httpcore, ctranslate2, coloredlogs, beautifulsoup4, anyio, youtube-transcript-api, pydantic, onnxruntime, huggingface-hub, httpx, tokenizers, openai, anthropic, faster-whisper

Successfully installed annotated-types-0.7.0 anthropic-0.64.0 anyio-4.10.0 av-15.1.0 beautifulsoup4-4.13.5 certifi-2025.8.3 charset_normalizer-3.4.3 coloredlogs-15.0.1 ctranslate2-4.6.0 defusedxml-0.7.1 distro-1.9.0 faster-whisper-1.2.0 feedparser-6.0.11 filelock-3.19.1 flatbuffers-25.2.10 fsspec-2025.7.0 h11-0.16.0 hf-xet-1.1.9 httpcore-1.0.9 httpx-0.28.1 huggingface-hub-0.34.4 humanfriendly-10.0 idna-3.10 jiter-0.10.0 mpmath-1.3.0 numpy-2.3.2 onnxruntime-1.22.1 openai-1.102.0 packaging-25.0 protobuf-6.32.0 pydantic-2.11.7 pydantic-core-2.33.2 python-dateutil-2.9.0.post0 python-dotenv-1.1.1 pyyaml-6.0.2 requests-2.32.5 sgmllib3k-1.0.0 six-1.17.0 sniffio-1.3.1 soupsieve-2.8 sympy-1.14.0 tokenizers-0.22.0 tqdm-4.67.1 typing-extensions-4.15.0 typing-inspection-0.4.1 urllib3-2.5.0 youtube-transcript-api-1.2.2
6s
Run awalsh128/cache-apt-pkgs-action@latest
Run ${GITHUB_ACTION_PATH}/pre_cache_action.sh \
Normalizing package list...
done
Validating action arguments (version='1', packages='ffmpeg=7:6.1.1-3ubuntu5 sqlite3=3.45.1-1ubuntu2.4')...
done

Creating cache key...
- CPU architecture is 'x86_64'.
- Value to hash is 'ffmpeg=7:6.1.1-3ubuntu5 sqlite3=3.45.1-1ubuntu2.4 @ 1 3'.
- Value hashed as 'ef433786b4f6fefed370461c007e017b'.
done
Hash value written to /home/runner/cache-apt-pkgs/cache_key.md5
Run actions/cache/restore@v4
Cache hit for: cache-apt-pkgs_ef433786b4f6fefed370461c007e017b
Received 20971520 of 105744605 (19.8%), 19.9 MBs/sec
Received 105744605 of 105744605 (100.0%), 60.6 MBs/sec
Cache Size: ~101 MB (105744605 B)
/usr/bin/tar -xf /home/runner/work/_temp/96c71169-05ca-4e45-846d-974c93063c43/cache.tzst -P -C /home/runner/work/podcast-scraper/podcast-scraper --use-compress-program unzstd
Cache restored successfully
Cache restored from key: cache-apt-pkgs_ef433786b4f6fefed370461c007e017b
Run ${GITHUB_ACTION_PATH}/post_cache_action.sh \
Found 103 files in the cache.
- cache_key.md5
- ffmpeg=7:6.1.1-3ubuntu5.tar
- i965-va-driver=2.4.1+dfsg1-1build2.tar
- install.log
- intel-media-va-driver=24.1.0+dfsg1-1ubuntu0.1.tar
- libaacs0=0.11.1-2build1.tar
- libass9=1:0.17.1-2build1.tar
- libasyncns0=0.8-6build4.tar
- libavc1394-0=0.5.4-5build3.tar
- libavcodec60=7:6.1.1-3ubuntu5.tar
- libavdevice60=7:6.1.1-3ubuntu5.tar
- libavfilter9=7:6.1.1-3ubuntu5.tar
- libavformat60=7:6.1.1-3ubuntu5.tar
- libavutil58=7:6.1.1-3ubuntu5.tar
- libbdplus0=0.2.0-3build1.tar
- libblas3=3.12.0-3build1.1.tar
- libbluray2=1:1.3.4-1build1.tar
- libbs2b0=3.1.0+dfsg-7build1.tar
- libcaca0=0.99.beta20-4build2.tar
- libcdio-cdda2t64=10.2+2.0.1-1.1build2.tar
- libcdio-paranoia2t64=10.2+2.0.1-1.1build2.tar
- libcdio19t64=2.1.0-4.1ubuntu1.2.tar
- libchromaprint1=1.5.1-5.tar
- libcjson1=1.7.17-1.tar
- libcodec2-1.2=1.2.0-2build1.tar
- libdav1d7=1.4.1-1build1.tar
- libdc1394-25=2.2.6-4build1.tar
- libdecor-0-0=0.2.2-1build2.tar
- libdecor-0-plugin-1-gtk=0.2.2-1build2.tar
- libflac12t64=1.4.3+ds-2.1ubuntu2.tar
- libflite1=2.2-6build3.tar
- libgme0=0.6.3-7build1.tar
- libgsm1=1.0.22-1build1.tar
- libhwy1t64=1.0.7-8.1build1.tar
- libiec61883-0=1.2.0-6build1.tar
- libigdgmm12=22.3.17+ds1-1.tar
- libjack-jackd2-0=1.9.21~dfsg-3ubuntu3.tar
- libjxl0.7=0.7.0-10.2ubuntu6.1.tar
- liblapack3=3.12.0-3build1.1.tar
- liblilv-0-0=0.24.22-1build1.tar
- libmbedcrypto7t64=2.28.8-1.tar
- libmp3lame0=3.100-6build1.tar
- libmpg123-0t64=1.32.5-1ubuntu1.1.tar
- libmysofa1=1.3.2+dfsg-2ubuntu2.tar
- libopenal-data=1:1.23.1-4build1.tar
- libopenal1=1:1.23.1-4build1.tar
- libopenmpt0t64=0.7.3-1.1build3.tar
- libopus0=1.4-1build1.tar
- libplacebo338=6.338.2-2build1.tar
- libpocketsphinx3=0.8.0+real5prealpha+1-15ubuntu5.tar
- libpostproc57=7:6.1.1-3ubuntu5.tar
- libpulse0=1:16.1+dfsg1-2ubuntu10.1.tar
- librav1e0=0.7.1-2.tar
- libraw1394-11=2.1.2-2build3.tar
- librist4=0.2.10+dfsg-2.tar
- librsvg2-2=2.58.0+dfsg-1build1.tar
- librsvg2-common=2.58.0+dfsg-1build1.tar
- librubberband2=3.3.0+dfsg-2build1.tar
- libsamplerate0=0.2.2-4build1.tar
- libsdl2-2.0-0=2.30.0+dfsg-1ubuntu3.1.tar
- libserd-0-0=0.32.2-1.tar
- libshine3=3.1.1-2build1.tar
- libsndfile1=1.2.2-1ubuntu5.24.04.1.tar
- libsndio7.0=1.9.0-0.3build3.tar
- libsord-0-0=0.16.16-2build1.tar
- libsoxr0=0.1.3-4build3.tar
- libspeex1=1.2.1-2ubuntu2.24.04.1.tar
- libsphinxbase3t64=0.8+5prealpha+1-17build2.tar
- libsratom-0-0=0.6.16-1build1.tar
- libsrt1.5-gnutls=1.5.3-1build2.tar
- libssh-gcrypt-4=0.10.6-2ubuntu0.1.tar
- libsvtav1enc1d1=1.7.0+dfsg-2build1.tar
- libswresample4=7:6.1.1-3ubuntu5.tar
- libswscale7=7:6.1.1-3ubuntu5.tar
- libtheora0=1.1.1+dfsg.1-16.1build3.tar
- libtwolame0=0.4.0-2build3.tar
- libudfread0=1.1.2-1build1.tar
- libunibreak5=5.1-2build1.tar
- libva-drm2=2.20.0-2build1.tar
- libva-x11-2=2.20.0-2build1.tar
- libva2=2.20.0-2build1.tar
- libvdpau1=1.5-2build1.tar
- libvidstab1.1=1.1.0-2build1.tar
- libvorbisenc2=1.3.7-1build3.tar
- libvpl2=2023.3.0-1build1.tar
- libvpx9=1.14.0-1ubuntu2.2.tar
- libx264-164=2:0.164.3108+git31e19f9-1.tar
- libx265-199=3.5-2build1.tar
- libxcb-shape0=1.15-1ubuntu2.tar
- libxv1=2:1.0.11-1.1build1.tar
- libxvidcore4=2:1.3.7-1build1.tar
- libzimg2=3.0.5+ds1-1build1.tar
- libzix-0-0=0.4.2-2build1.tar
- libzvbi-common=0.2.42-2.tar
- libzvbi0t64=0.2.42-2.tar
- manifest_all.log
- manifest_main.log
- mesa-va-drivers=25.0.7-0ubuntu0.24.04.1.tar
- mesa-vdpau-drivers=25.0.7-0ubuntu0.24.04.1.tar
- ocl-icd-libopencl1=2.3.2-1build1.tar
- pocketsphinx-en-us=0.8.0+real5prealpha+1-15ubuntu5.tar
- va-driver-all=2.20.0-2build1.tar
- vdpau-driver-all=1.5-2build1.tar

Reading from main requested packages manifest...
- ffmpeg=7 6.1.1-3ubuntu5
- sqlite3=3.45.1-1ubuntu2.4
done

Restoring 99 packages from cache...
- ffmpeg=7:6.1.1-3ubuntu5.tar restoring...
  done
- i965-va-driver=2.4.1+dfsg1-1build2.tar restoring...
  done
- intel-media-va-driver=24.1.0+dfsg1-1ubuntu0.1.tar restoring...
  done
- libaacs0=0.11.1-2build1.tar restoring...
  done
- libass9=1:0.17.1-2build1.tar restoring...
  done
- libasyncns0=0.8-6build4.tar restoring...
  done
- libavc1394-0=0.5.4-5build3.tar restoring...
  done
- libavcodec60=7:6.1.1-3ubuntu5.tar restoring...
  done
- libavdevice60=7:6.1.1-3ubuntu5.tar restoring...
  done
- libavfilter9=7:6.1.1-3ubuntu5.tar restoring...
  done
- libavformat60=7:6.1.1-3ubuntu5.tar restoring...
  done
- libavutil58=7:6.1.1-3ubuntu5.tar restoring...
  done
- libbdplus0=0.2.0-3build1.tar restoring...
  done
- libblas3=3.12.0-3build1.1.tar restoring...
  done
- libbluray2=1:1.3.4-1build1.tar restoring...
  done
- libbs2b0=3.1.0+dfsg-7build1.tar restoring...
  done
- libcaca0=0.99.beta20-4build2.tar restoring...
  done
- libcdio-cdda2t64=10.2+2.0.1-1.1build2.tar restoring...
  done
- libcdio-paranoia2t64=10.2+2.0.1-1.1build2.tar restoring...
  done
- libcdio19t64=2.1.0-4.1ubuntu1.2.tar restoring...
  done
- libchromaprint1=1.5.1-5.tar restoring...
  done
- libcjson1=1.7.17-1.tar restoring...
  done
- libcodec2-1.2=1.2.0-2build1.tar restoring...
  done
- libdav1d7=1.4.1-1build1.tar restoring...
  done
- libdc1394-25=2.2.6-4build1.tar restoring...
  done
- libdecor-0-0=0.2.2-1build2.tar restoring...
  done
- libdecor-0-plugin-1-gtk=0.2.2-1build2.tar restoring...
  done
- libflac12t64=1.4.3+ds-2.1ubuntu2.tar restoring...
  done
- libflite1=2.2-6build3.tar restoring...
  done
- libgme0=0.6.3-7build1.tar restoring...
  done
- libgsm1=1.0.22-1build1.tar restoring...
  done
- libhwy1t64=1.0.7-8.1build1.tar restoring...
  done
- libiec61883-0=1.2.0-6build1.tar restoring...
  done
- libigdgmm12=22.3.17+ds1-1.tar restoring...
  done
- libjack-jackd2-0=1.9.21~dfsg-3ubuntu3.tar restoring...
  done
- libjxl0.7=0.7.0-10.2ubuntu6.1.tar restoring...
  done
- liblapack3=3.12.0-3build1.1.tar restoring...
  done
- liblilv-0-0=0.24.22-1build1.tar restoring...
  done
- libmbedcrypto7t64=2.28.8-1.tar restoring...
  done
- libmp3lame0=3.100-6build1.tar restoring...
  done
- libmpg123-0t64=1.32.5-1ubuntu1.1.tar restoring...
  done
- libmysofa1=1.3.2+dfsg-2ubuntu2.tar restoring...
  done
- libopenal-data=1:1.23.1-4build1.tar restoring...
  done
- libopenal1=1:1.23.1-4build1.tar restoring...
  done
- libopenmpt0t64=0.7.3-1.1build3.tar restoring...
  done
- libopus0=1.4-1build1.tar restoring...
  done
- libplacebo338=6.338.2-2build1.tar restoring...
  done
- libpocketsphinx3=0.8.0+real5prealpha+1-15ubuntu5.tar restoring...
  done
- libpostproc57=7:6.1.1-3ubuntu5.tar restoring...
  done
- libpulse0=1:16.1+dfsg1-2ubuntu10.1.tar restoring...
  done
- librav1e0=0.7.1-2.tar restoring...
  done
- libraw1394-11=2.1.2-2build3.tar restoring...
  done
- librist4=0.2.10+dfsg-2.tar restoring...
  done
- librsvg2-2=2.58.0+dfsg-1build1.tar restoring...
  done
- librsvg2-common=2.58.0+dfsg-1build1.tar restoring...
  done
- librubberband2=3.3.0+dfsg-2build1.tar restoring...
  done
- libsamplerate0=0.2.2-4build1.tar restoring...
  done
- libsdl2-2.0-0=2.30.0+dfsg-1ubuntu3.1.tar restoring...
  done
- libserd-0-0=0.32.2-1.tar restoring...
  done
- libshine3=3.1.1-2build1.tar restoring...
  done
- libsndfile1=1.2.2-1ubuntu5.24.04.1.tar restoring...
  done
- libsndio7.0=1.9.0-0.3build3.tar restoring...
  done
- libsord-0-0=0.16.16-2build1.tar restoring...
  done
- libsoxr0=0.1.3-4build3.tar restoring...
  done
- libspeex1=1.2.1-2ubuntu2.24.04.1.tar restoring...
  done
- libsphinxbase3t64=0.8+5prealpha+1-17build2.tar restoring...
  done
- libsratom-0-0=0.6.16-1build1.tar restoring...
  done
- libsrt1.5-gnutls=1.5.3-1build2.tar restoring...
  done
- libssh-gcrypt-4=0.10.6-2ubuntu0.1.tar restoring...
  done
- libsvtav1enc1d1=1.7.0+dfsg-2build1.tar restoring...
  done
- libswresample4=7:6.1.1-3ubuntu5.tar restoring...
  done
- libswscale7=7:6.1.1-3ubuntu5.tar restoring...
  done
- libtheora0=1.1.1+dfsg.1-16.1build3.tar restoring...
  done
- libtwolame0=0.4.0-2build3.tar restoring...
  done
- libudfread0=1.1.2-1build1.tar restoring...
  done
- libunibreak5=5.1-2build1.tar restoring...
  done
- libva-drm2=2.20.0-2build1.tar restoring...
  done
- libva-x11-2=2.20.0-2build1.tar restoring...
  done
- libva2=2.20.0-2build1.tar restoring...
  done
- libvdpau1=1.5-2build1.tar restoring...
  done
- libvidstab1.1=1.1.0-2build1.tar restoring...
  done
- libvorbisenc2=1.3.7-1build3.tar restoring...
  done
- libvpl2=2023.3.0-1build1.tar restoring...
  done
- libvpx9=1.14.0-1ubuntu2.2.tar restoring...
  done
- libx264-164=2:0.164.3108+git31e19f9-1.tar restoring...
  done
- libx265-199=3.5-2build1.tar restoring...
  done
- libxcb-shape0=1.15-1ubuntu2.tar restoring...
  done
- libxv1=2:1.0.11-1.1build1.tar restoring...
  done
- libxvidcore4=2:1.3.7-1build1.tar restoring...
  done
- libzimg2=3.0.5+ds1-1build1.tar restoring...
  done
- libzix-0-0=0.4.2-2build1.tar restoring...
  done
- libzvbi-common=0.2.42-2.tar restoring...
  done
- libzvbi0t64=0.2.42-2.tar restoring...
  done
- mesa-va-drivers=25.0.7-0ubuntu0.24.04.1.tar restoring...
  done
- mesa-vdpau-drivers=25.0.7-0ubuntu0.24.04.1.tar restoring...
  done
- ocl-icd-libopencl1=2.3.2-1build1.tar restoring...
  done
- pocketsphinx-en-us=0.8.0+real5prealpha+1-15ubuntu5.tar restoring...
  done
- va-driver-all=2.20.0-2build1.tar restoring...
  done
- vdpau-driver-all=1.5-2build1.tar restoring...
  done
done

Run rm -rf ~/cache-apt-pkgs
0s
Run echo "🎯 Workflow Mode: normal"
🎯 Workflow Mode: normal
🐛 Debug Mode: false
⚡ Trigger: workflow_dispatch
📅 Current day: Tuesday
📆 REGULAR WEEKDAY: Standard daily processing
0s
Run # Validate required API keys are present before setting
✅ ANTHROPIC_API_KEY is set (length: 108)
✅ OPENAI_API_KEY is set (length: 164)
4m 57s
Run if [ "false" == "true" ]; then
🚀 Regular weekday processing mode
INFO:openai_scorer:✅ OpenAI client initialized successfully
INFO:prose_validator:✅ Prose validator OpenAI client initialized
INFO:openai_digest_integration:✅ OpenAI API client initialized (key length: 164)
INFO:__main__:🚀 Starting GITHUB ACTIONS Pipeline
INFO:__main__:📝 GITHUB SCOPE: RSS processing + YouTube transcripts + Digest generation
INFO:__main__:===========================================================================
From https://github.com/McSchnizzle/podcast-scraper
 * branch            main       -> FETCH_HEAD
Already up to date.
INFO:__main__:✅ Pulled latest changes - YouTube transcripts already in repo
INFO:__main__:📡 Checking RSS feeds for new episodes...
INFO:__main__:No new episodes found
INFO:__main__:🎵 Processing audio cache files...
INFO:__main__:No MP3 files found in audio_cache
INFO:__main__:⚙️ Processing episodes awaiting transcription (pending/pre-download)...
INFO:__main__:No pending episodes to process
INFO:__main__:📊 Generating digest from ALL 'transcribed' episodes (RSS + YouTube)
INFO:__main__:📝 Generating daily digest from RSS + YouTube transcripts...
INFO:__main__:📊 RSS Episode status breakdown:
INFO:__main__:   archived: 2 episodes
INFO:__main__:   downloaded: 1 episodes
INFO:__main__:📊 YouTube Episode status breakdown:
INFO:__main__:   digested: 2 episodes
INFO:__main__:   transcribed: 8 episodes
INFO:__main__:📋 Total transcripts for digest: 0 RSS + 8 YouTube = 8
INFO:openai_digest_integration:🧠 Starting multi-topic digest generation
INFO:openai_digest_integration:🚀 Starting multi-topic digest generation for 4 topics
INFO:openai_digest_integration:Topics: AI News, Societal Culture Change, Tech News and Tech Culture, Tech Product Releases
INFO:openai_digest_integration:
📝 Processing topic: AI News
INFO:openai_digest_integration:🧠 Starting AI News digest generation with OpenAI GPT-5
INFO:openai_digest_integration:Found 0 RSS transcripts
INFO:openai_digest_integration:Found 8 YouTube transcripts
INFO:openai_digest_integration:Total transcripts for analysis: 8
INFO:openai_digest_integration:📊 Analyzing 8 transcripts for AI News
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 429 Too Many Requests"
INFO:openai._base_client:Retrying request to /chat/completions in 0.486851 seconds
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 429 Too Many Requests"
INFO:openai._base_client:Retrying request to /chat/completions in 0.917839 seconds
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 429 Too Many Requests"
ERROR:openai_digest_integration:Error generating AI News digest with OpenAI GPT-5: Error code: 429 - {'error': {'message': 'Request too large for gpt-4-turbo-preview in organization org-YDQA8AmUqoik8dPmIQfG34Lf on tokens per min (TPM): Limit 30000, Requested 34238. The input or output tokens must be reduced in order to run successfully. Visit https://platform.openai.com/account/rate-limits to learn more.', 'type': 'tokens', 'param': None, 'code': 'rate_limit_exceeded'}}
ERROR:openai_digest_integration:❌ AI News digest failed: Error code: 429 - {'error': {'message': 'Request too large for gpt-4-turbo-preview in organization org-YDQA8AmUqoik8dPmIQfG34Lf on tokens per min (TPM): Limit 30000, Requested 34238. The input or output tokens must be reduced in order to run successfully. Visit https://platform.openai.com/account/rate-limits to learn more.', 'type': 'tokens', 'param': None, 'code': 'rate_limit_exceeded'}}
INFO:openai_digest_integration:
📝 Processing topic: Societal Culture Change
INFO:openai_digest_integration:🧠 Starting Societal Culture Change digest generation with OpenAI GPT-5
INFO:openai_digest_integration:Found 0 RSS transcripts
INFO:openai_digest_integration:Found 1 YouTube transcripts
INFO:openai_digest_integration:Total transcripts for analysis: 1
INFO:openai_digest_integration:📊 Analyzing 1 transcripts for Societal Culture Change
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO:openai_digest_integration:🔍 Validating prose quality for Societal Culture Change digest
INFO:prose_validator:❌ Text validation failed: Contains too many headers (11/20 lines), Too many short lines (9/20), likely fragmented text
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO:prose_validator:✅ Successfully rewrote text to prose (attempt 1)
INFO:openai_digest_integration:✅ Societal Culture Change digest was rewritten to improve prose quality
INFO:openai_digest_integration:✅ Societal Culture Change digest saved to daily_digests/societal_culture_change_digest_20250902_005315.md
INFO:openai_digest_integration:✅ Marked 1 YouTube episodes as digested for Societal Culture Change
INFO:openai_digest_integration:📁 Moved 4746906a.txt to digested folder
INFO:openai_digest_integration:✅ Societal Culture Change digest completed: daily_digests/societal_culture_change_digest_20250902_005315.md
INFO:openai_digest_integration:
📝 Processing topic: Tech News and Tech Culture
INFO:openai_digest_integration:🧠 Starting Tech News and Tech Culture digest generation with OpenAI GPT-5
INFO:openai_digest_integration:Found 0 RSS transcripts
INFO:openai_digest_integration:Found 7 YouTube transcripts
INFO:openai_digest_integration:Total transcripts for analysis: 7
INFO:openai_digest_integration:📊 Analyzing 7 transcripts for Tech News and Tech Culture
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO:openai_digest_integration:🔍 Validating prose quality for Tech News and Tech Culture digest
INFO:prose_validator:❌ Text validation failed: Contains too many headers (11/24 lines)
INFO:httpx:HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO:prose_validator:✅ Successfully rewrote text to prose (attempt 1)
INFO:openai_digest_integration:✅ Tech News and Tech Culture digest was rewritten to improve prose quality
INFO:openai_digest_integration:✅ Tech News and Tech Culture digest saved to daily_digests/tech_news_and_tech_culture_digest_20250902_005409.md
INFO:openai_digest_integration:✅ Marked 7 YouTube episodes as digested for Tech News and Tech Culture
INFO:openai_digest_integration:📁 Moved 4cd9eaba.txt to digested folder
INFO:openai_digest_integration:📁 Moved 96e71ad6.txt to digested folder
INFO:openai_digest_integration:📁 Moved 39716c6b.txt to digested folder
INFO:openai_digest_integration:📁 Moved dbfbc72b.txt to digested folder
INFO:openai_digest_integration:📁 Moved 37b115ce.txt to digested folder
INFO:openai_digest_integration:📁 Moved 6e2a787a.txt to digested folder
INFO:openai_digest_integration:📁 Moved ed9386ee.txt to digested folder
INFO:openai_digest_integration:✅ Tech News and Tech Culture digest completed: daily_digests/tech_news_and_tech_culture_digest_20250902_005409.md
INFO:openai_digest_integration:
📝 Processing topic: Tech Product Releases
INFO:openai_digest_integration:🧠 Starting Tech Product Releases digest generation with OpenAI GPT-5
INFO:openai_digest_integration:Found 0 RSS transcripts
INFO:openai_digest_integration:Found 0 YouTube transcripts
INFO:openai_digest_integration:Total transcripts for analysis: 0
WARNING:openai_digest_integration:No transcripts available for topic: Tech Product Releases
ERROR:openai_digest_integration:❌ Tech Product Releases digest failed: None
INFO:openai_digest_integration:
🏁 Multi-topic digest generation complete: 2/4 topics successful
INFO:__main__:✅ Daily digest generated: daily_digests/societal_culture_change_digest_20250902_005315.md
INFO:__main__:🎙️ Creating TTS audio...
INFO:__main__:========================================
INFO:__main__:🔥 TTS GENERATION - CRITICAL DEBUG INFO
INFO:__main__:========================================
INFO:__main__:✅ ELEVENLABS_API_KEY found (length: 51)
INFO:__main__:📄 Found 4 digest files: ['daily_digest_20250901_113824.md', 'daily_digest_20250901_115502.md', 'daily_digest_20250901_013235.md', 'daily_digest_20250901_015602.md']
INFO:__main__:📁 Current directory contents:
INFO:__main__:   📄 episode_summaries.db
INFO:__main__:   📄 .vercelignore
INFO:__main__:   📄 claude_api_integration.py
INFO:__main__:   📄 README.md
INFO:__main__:   📄 requirements.txt
INFO:__main__:   📄 setup_music_library.py
INFO:__main__:   📄 manage_feeds.py
INFO:__main__:   📄 podcast_data.db
INFO:__main__:   📄 rss_generator_multi_topic.py
INFO:__main__:   📄 advertisement_examples.txt
INFO:__main__:   📄 fix_malloc_warnings.sh
INFO:__main__:   📄 CLAUDE.md
INFO:__main__:   📄 parakeet-time-estimate.docx
INFO:__main__:   📄 youtube_transcripts.db.backup.20250901-170835.db
INFO:__main__:   📄 podscraper_prd.md
INFO:__main__:   📄 test_transcript_with_ads.txt
INFO:__main__:   📄 claude_daily_digest_20250829_215442.md
INFO:__main__:   📄 deploy_multi_topic.py
INFO:__main__:   📄 claude_headless_integration.py
INFO:__main__:   📄 prep_test_data_auto.py
INFO:__main__:   📄 robust_transcriber.py
INFO:__main__:   📄 podcast_monitor.db.backup
INFO:__main__:   📄 deploy_episode.py
INFO:__main__:   📄 daily-digest.xml
INFO:__main__:   📄 podcast_monitor.db.backup.20250901-174655.db
INFO:__main__:   📄 claude_daily_digest_20250828_170909.md
INFO:__main__:   📄 daily_podcast_pipeline.py
INFO:__main__:   📄 DUAL_DATABASE_README.md
INFO:__main__:   📄 youtube_transcripts.db
INFO:__main__:   📄 restore_feeds.py
INFO:__main__:   📄 deployed_episodes.json
INFO:__main__:   📄 setup_cron.sh
INFO:__main__:   📄 youtube_transcripts.db.backup.20250901-170602.db
INFO:__main__:   📄 podcast_monitor.db.backup.20250901-170547.db
INFO:__main__:   📄 claude_cross_references_20250828_165735.json
INFO:__main__:   📄 content_processor.py
INFO:__main__:   📄 claude_cross_references_20250829_215442.json
INFO:__main__:   📄 rss_generator.py
INFO:__main__:   📄 claude_daily_digest_20250829_222116.md
INFO:__main__:   📄 claude_daily_digest_20250828_215104.md
INFO:__main__:   📄 .env.example
INFO:__main__:   📄 openai_scorer.py
INFO:__main__:   📄 youtube_transcripts.db.backup.20250901-174655.db
INFO:__main__:   📄 multi_topic_tts_generator.py
INFO:__main__:   📄 claude_digest_instructions.md
INFO:__main__:   📄 youtube_transcripts.db.backup.20250901-170547.db
INFO:__main__:   📄 test_output_basic.txt
INFO:__main__:   📄 youtube_processor.py
INFO:__main__:   📄 config.py
INFO:__main__:   📄 openai_digest_integration.py
INFO:__main__:   📄 music_integration.py
INFO:__main__:   📄 requirements-dev.txt
INFO:__main__:   📄 podcast_monitor.db.backup.20250901-170602.db
INFO:__main__:   📄 youtube_cron_job.sh
INFO:__main__:   📄 setup_youtube_automation.py
INFO:__main__:   📄 claude_cross_references_20250829_222116.json
INFO:__main__:   📄 podcast_monitor.db.backup.20250901-170835.db
INFO:__main__:   📄 backfill_missing_scores.py
INFO:__main__:   📄 scraper-improvements.docx
INFO:__main__:   📄 retention_cleanup.py
INFO:__main__:   📄 topic_moderator.py
INFO:__main__:   📄 podcast_monitor.db
INFO:__main__:   📄 topics.json
INFO:__main__:   📄 claude_daily_digest_20250828_165735.md
INFO:__main__:   📄 test_output_claude.txt
INFO:__main__:   📄 feed_monitor.py
INFO:__main__:   📄 .gitignore
INFO:__main__:   📄 vercel.json
INFO:__main__:   📄 vercel-build-ignore.sh
INFO:__main__:   📄 prose_validator.py
INFO:__main__:   📄 youtube_transcripts.db.backup
INFO:__main__:   📄 setup_cron.py
INFO:__main__:   📄 ~$raper-improvements.docx
INFO:__main__:   📄 episode_summary_generator.py
INFO:__main__:   📄 claude_cross_references_20250828_215104.json
INFO:__main__:   📄 claude_tts_generator.py
INFO:__main__:🚀 Running multi-topic TTS generation subprocess...
INFO:__main__:Command: python3 multi_topic_tts_generator.py
INFO:__main__:🔍 TTS subprocess return code: 0
INFO:__main__:🔍 TTS subprocess stdout length: 45
INFO:__main__:🔍 TTS subprocess stderr length: 4432
INFO:__main__:📝 TTS subprocess STDOUT:
INFO:__main__:   STDOUT: 🎙️  Successfully generated 2 TTS audio files
ERROR:__main__:📝 TTS subprocess STDERR:
ERROR:__main__:   STDERR: INFO:__main__:✅ Loaded voice config for 6 topics
ERROR:__main__:   STDERR: INFO:__main__:🎵 Music integration enabled
ERROR:__main__:   STDERR: INFO:__main__:🎯 Found 2 unprocessed digest files
ERROR:__main__:   STDERR: INFO:__main__:🔄 Processing societal_culture_change digest (20250902_005315)
ERROR:__main__:   STDERR: INFO:__main__:📝 TTS-optimized script saved: societal_culture_change_digest_tts_20250902_005315.txt
ERROR:__main__:   STDERR: INFO:__main__:🎙️  Generating TTS audio: societal_culture_change_digest_20250902_005315
ERROR:__main__:   STDERR: INFO:__main__:✅ TTS audio generated: societal_culture_change_digest_20250902_005315.mp3 (4,901,034 bytes)
ERROR:__main__:   STDERR: INFO:__main__:🎵 Adding music enhancement for societal_culture_change
ERROR:__main__:   STDERR: INFO:music_integration:🎧 Adding intro/outro music with crossfade for societal_culture_change
ERROR:__main__:   STDERR: INFO:music_integration:🎵 Generating 60s master music for societal_culture_change
ERROR:__main__:   STDERR: INFO:music_integration:✅ Generated master music: societal_culture_change_master_60s.mp3 (960097 bytes)
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Failed to extract segment: ffmpeg: error while loading shared libraries: libblas.so.3: cannot open shared object file: No such file or directory
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Failed to generate intro segment
ERROR:__main__:   STDERR: INFO:music_integration:📻 Using cached master music: societal_culture_change_master_60s.mp3
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Failed to extract segment: ffmpeg: error while loading shared libraries: libblas.so.3: cannot open shared object file: No such file or directory
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Failed to generate outro segment
ERROR:__main__:   STDERR: INFO:music_integration:🎵 Creating static music files as fallback...
ERROR:__main__:   STDERR: INFO:music_integration:🔄 Adding crossfade intro/outro music...
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Crossfade enhancement failed: ffmpeg: error while loading shared libraries: libblas.so.3: cannot open shared object file: No such file or directory
ERROR:__main__:   STDERR: INFO:music_integration:🔄 Trying fallback with simple overlay...
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Fallback also failed: ffmpeg: error while loading shared libraries: libblas.so.3: cannot open shared object file: No such file or directory
ERROR:__main__:   STDERR: INFO:music_integration:📄 Final fallback: copied original audio to daily_digests/societal_culture_change_digest_20250902_005315_enhanced.mp3
ERROR:__main__:   STDERR: INFO:__main__:📄 Metadata saved: societal_culture_change_digest_20250902_005315.json
ERROR:__main__:   STDERR: INFO:__main__:✅ Successfully processed societal_culture_change digest
ERROR:__main__:   STDERR: INFO:__main__:🔄 Processing tech_news_and_tech_culture digest (20250902_005409)
ERROR:__main__:   STDERR: INFO:__main__:📝 TTS-optimized script saved: tech_news_and_tech_culture_digest_tts_20250902_005409.txt
ERROR:__main__:   STDERR: INFO:__main__:🎙️  Generating TTS audio: tech_news_and_tech_culture_digest_20250902_005409
ERROR:__main__:   STDERR: INFO:__main__:✅ TTS audio generated: tech_news_and_tech_culture_digest_20250902_005409.mp3 (5,059,440 bytes)
ERROR:__main__:   STDERR: INFO:__main__:🎵 Adding music enhancement for tech_news_and_tech_culture
ERROR:__main__:   STDERR: INFO:music_integration:🎧 Adding intro/outro music with crossfade for tech_news_and_tech_culture
ERROR:__main__:   STDERR: INFO:music_integration:🎵 Generating 60s master music for tech_news_and_tech_culture
ERROR:__main__:   STDERR: INFO:music_integration:✅ Generated master music: tech_news_and_tech_culture_master_60s.mp3 (960097 bytes)
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Failed to extract segment: ffmpeg: error while loading shared libraries: libblas.so.3: cannot open shared object file: No such file or directory
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Failed to generate intro segment
ERROR:__main__:   STDERR: INFO:music_integration:📻 Using cached master music: tech_news_and_tech_culture_master_60s.mp3
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Failed to extract segment: ffmpeg: error while loading shared libraries: libblas.so.3: cannot open shared object file: No such file or directory
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Failed to generate outro segment
ERROR:__main__:   STDERR: INFO:music_integration:🎵 Creating static music files as fallback...
ERROR:__main__:   STDERR: INFO:music_integration:🔄 Adding crossfade intro/outro music...
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Crossfade enhancement failed: ffmpeg: error while loading shared libraries: libblas.so.3: cannot open shared object file: No such file or directory
ERROR:__main__:   STDERR: INFO:music_integration:🔄 Trying fallback with simple overlay...
ERROR:__main__:   STDERR: ERROR:music_integration:❌ Fallback also failed: ffmpeg: error while loading shared libraries: libblas.so.3: cannot open shared object file: No such file or directory
ERROR:__main__:   STDERR: INFO:music_integration:📄 Final fallback: copied original audio to daily_digests/tech_news_and_tech_culture_digest_20250902_005409_enhanced.mp3
ERROR:__main__:   STDERR: INFO:__main__:📄 Metadata saved: tech_news_and_tech_culture_digest_20250902_005409.json
ERROR:__main__:   STDERR: INFO:__main__:✅ Successfully processed tech_news_and_tech_culture digest
ERROR:__main__:   STDERR: INFO:__main__:📊 Processing complete: 2 successful, 0 failed
INFO:__main__:📁 Post-TTS daily_digests directory:
INFO:__main__:   📄 ai_news_digest_20250901_203850.mp3 (4099386 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_203850.md (3405 bytes)
INFO:__main__:   📄 claude_digest_full_20250829_222259.txt (5450 bytes)
INFO:__main__:   📄 tech_news_and_tech_culture_digest_20250902_005409_enhanced.mp3 (5059440 bytes)
INFO:__main__:   📄 daily_digest_20250901_113824.md (2672 bytes)
INFO:__main__:   📄 daily_digest_20250901_113824.json (590 bytes)
INFO:__main__:   📄 claude_digest_tts_20250901_015602.txt (3328 bytes)
INFO:__main__:   📄 societal_culture_change_digest_tts_20250902_005315.txt (4208 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_204213.json (643 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_175357.mp3 (3872436 bytes)
INFO:__main__:   📄 daily_digest_20250901_115502.md (2631 bytes)
INFO:__main__:   📄 daily_digest_20250901_113824_enhanced.mp3 (3566490 bytes)
INFO:__main__:   📄 tech_news_and_tech_culture_digest_20250902_005409.json (710 bytes)
INFO:__main__:   📄 tech_news_and_tech_culture_digest_tts_20250902_005409.txt (4792 bytes)
INFO:__main__:   📄 daily_digest_20250901_013235_enhanced.mp3 (4241076 bytes)
INFO:__main__:   📄 daily_digest_20250901_113824.mp3 (3566490 bytes)
INFO:__main__:   📄 claude_digest_tts_20250901_115502.txt (2764 bytes)
INFO:__main__:   📄 ai_news_digest_tts_20250901_204213.txt (4224 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_175357.json (643 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_171631_enhanced.mp3 (3009351 bytes)
INFO:__main__:   📄 daily_digest_tts_20250901_015602.txt (3328 bytes)
INFO:__main__:   📄 societal_culture_change_digest_20250902_005315_enhanced.mp3 (4901034 bytes)
INFO:__main__:   📄 daily_digest_tts_20250901_113824.txt (2820 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_203850.json (643 bytes)
INFO:__main__:   📄 societal_culture_change_digest_20250902_005315.md (4184 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_204213.md (4194 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_171626.md (2411 bytes)
INFO:__main__:   📄 claude_digest_tts_20250829_222259.txt (5750 bytes)
INFO:__main__:   📄 societal_culture_change_digest_20250902_005315.json (708 bytes)
INFO:__main__:   📄 complete_topic_digest_20250901_013235.json (442 bytes)
INFO:__main__:   📄 daily_digest_20250901_013235.md (3230 bytes)
INFO:__main__:   📄 daily_digest_20250901_013235.mp3 (4241076 bytes)
INFO:__main__:   📄 complete_topic_digest_20250901_013235.mp3 (4217253 bytes)
INFO:__main__:   📄 claude_digest_full_20250901_015602.txt (3230 bytes)
INFO:__main__:   📄 tech_news_and_tech_culture_digest_20250902_005409.mp3 (5059440 bytes)
INFO:__main__:   📄 complete_topic_digest_20250829_222259.json (410 bytes)
INFO:__main__:   📄 daily_digest_20250901_115502.json (590 bytes)
INFO:__main__:   📄 daily_digest_20250901_015602.md (3230 bytes)
INFO:__main__:   📄 complete_topic_digest_20250901_015602.json (442 bytes)
INFO:__main__:   📄 daily_digest_tts_20250901_013235.txt (3328 bytes)
INFO:__main__:   📄 claude_digest_full_20250901_013235.txt (3230 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_171626.mp3 (2491499 bytes)
INFO:__main__:   📄 daily_digest_20250901_115502.mp3 (3486242 bytes)
INFO:__main__:   📄 claude_digest_full_20250901_113824.txt (2672 bytes)
INFO:__main__:   📄 tech_news_and_tech_culture_digest_20250902_005409.md (4761 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_171631.json (643 bytes)
INFO:__main__:   📄 daily_digest_20250901_015602_enhanced.mp3 (4222686 bytes)
INFO:__main__:   📄 daily_digest_20250901_015602.json (590 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_171631.md (2780 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_171626_enhanced.mp3 (2491499 bytes)
INFO:__main__:   📄 daily_digest_20250901_013235.json (590 bytes)
INFO:__main__:   📄 claude_digest_tts_20250901_113824.txt (2820 bytes)
INFO:__main__:   📄 complete_topic_digest_20250901_115502.json (445 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_171626.json (643 bytes)
INFO:__main__:   📄 complete_topic_digest_20250829_215551.json (284 bytes)
INFO:__main__:   📄 ai_news_digest_tts_20250901_171626.txt (2432 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_175357_enhanced.mp3 (3872436 bytes)
INFO:__main__:   📄 societal_culture_change_digest_20250902_005315.mp3 (4901034 bytes)
INFO:__main__:   📄 daily_digest_tts_20250901_115502.txt (2764 bytes)
INFO:__main__:   📄 complete_topic_digest_20250901_015602.mp3 (4263646 bytes)
INFO:__main__:   📄 complete_topic_digest_20250901_115502.mp3 (3499617 bytes)
INFO:__main__:   📄 daily_digest_20250901_115502_enhanced.mp3 (3486242 bytes)
INFO:__main__:   📄 ai_news_digest_tts_20250901_175357.txt (3524 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_171631.mp3 (3009351 bytes)
INFO:__main__:   📄 claude_digest_tts_20250901_013235.txt (3328 bytes)
INFO:__main__:   📄 ai_news_digest_tts_20250901_171631.txt (2801 bytes)
INFO:__main__:   📄 claude_digest_full_20250901_115502.txt (2631 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_175357.md (3501 bytes)
INFO:__main__:   📄 ai_news_digest_20250901_204213.mp3 (4890165 bytes)
INFO:__main__:   📄 daily_digest_20250901_015602.mp3 (4222686 bytes)
INFO:__main__:   📄 ai_news_digest_tts_20250901_203850.txt (3429 bytes)
INFO:__main__:🎵 Found 3 audio files: ['complete_topic_digest_20250901_013235.mp3', 'complete_topic_digest_20250901_015602.mp3', 'complete_topic_digest_20250901_115502.mp3']
INFO:__main__:✅ TTS audio generated successfully with audio files!
INFO:__main__:========================================
INFO:__main__:🚀 Deploying to GitHub...
ERROR:__main__:❌ GitHub deployment failed: 
INFO:__main__:📡 Updating RSS feed...
INFO:__main__:✅ RSS feed updated successfully
INFO:__main__:📋 Marking episodes as digested in both RSS and YouTube databases...
INFO:__main__:✅ Marked episodes as digested: 0 RSS + 0 YouTube = 0 total
INFO:__main__:🧹 Running 14-day retention cleanup...
INFO:retention_cleanup:🗑️  Initializing retention cleanup (keep last 14 days)
INFO:retention_cleanup:🗓️  Cutoff date: 2025-08-19 00:57:17
INFO:retention_cleanup:🚀 Starting 14-day retention cleanup process
INFO:retention_cleanup:🔍 Checking transcripts for old files...
INFO:retention_cleanup:🔍 Checking transcripts/digested for old files...
INFO:retention_cleanup:✅ Removed 0 transcript files (0 bytes freed)
INFO:retention_cleanup:🔍 Checking daily_digests for old digest files...
INFO:retention_cleanup:✅ Removed 0 digest files (0 bytes freed)
INFO:retention_cleanup:🗄️  Cleaning heavy fields in podcast_monitor.db
INFO:retention_cleanup:  ✅ No old episodes with heavy fields found
INFO:retention_cleanup:🗄️  Cleaning heavy fields in youtube_transcripts.db
INFO:retention_cleanup:  ✅ No old episodes with heavy fields found
INFO:retention_cleanup:🧹 Running VACUUM on podcast_monitor.db
INFO:retention_cleanup:  ✅ VACUUM completed: 0 bytes freed
INFO:retention_cleanup:🧹 Running VACUUM on youtube_transcripts.db
INFO:retention_cleanup:  ✅ VACUUM completed: 0 bytes freed
INFO:retention_cleanup:📊 Retention cleanup summary:
INFO:retention_cleanup:  📁 Files removed: 0
INFO:retention_cleanup:  💾 Bytes freed: 0
INFO:retention_cleanup:  🗄️  Episodes cleaned: 0
INFO:retention_cleanup:  🧹 Database vacuum: ✅ Success
INFO:__main__:✅ No cleanup needed - all files within retention period
INFO:__main__:✅ GITHUB ACTIONS workflow completed successfully
INFO:__main__:🔄 Local machine will pull digest status updates on next run
✅ Faster-Whisper available - using optimized cross-platform ASR
⚡ Using Faster-Whisper (4x faster cross-platform)
Initializing Faster-Whisper models...
Loading Faster-Whisper model: medium
✅ Faster-Whisper ASR model loaded successfully
⚡ Using optimized CTranslate2 engine (4x faster)
🔧 GitHub Actions mode: Only checking RSS feeds (YouTube processed locally)
Checking The Vergecast...
Checking Leading the Shift: AI innovation talks with Microsoft Azure...
Checking The Diary Of A CEO with Steven Bartlett...
Checking Slo Mo: A Podcast with Mo Gawdat...
Checking Team Human...
Checking The Great Simplification with Nate Hagens...
Checking THIS IS REVOLUTION ＞podcast...
Checking The Red Nation Podcast...
Checking Movement Memos...
Checking Real Sankara Hours...
Checking Millennials Are Killing Capitalism...
Checking The Black Myths Podcast...
Checking The Malcolm Effect...
Checking The Dugout | a black anarchist podcast...
Checking Black Autonomy Podcast...
0s
Run echo "=========================================="
==========================================
🎵 TTS GENERATION DEBUGGING (CRITICAL)
==========================================
=== Environment Variables ===
ELEVENLABS_API_KEY length: 51
ANTHROPIC_API_KEY length: 108
✅ ELEVENLABS_API_KEY is set
=== Daily Digests Directory ===
total 88820
drwxr-xr-x  2 runner docker    4096 Sep  2 00:57 .
drwxr-xr-x 14 runner docker    4096 Sep  2 00:57 ..
-rw-r--r--  1 runner docker     643 Sep  2 00:51 ai_news_digest_20250901_171626.json
-rw-r--r--  1 runner docker    2411 Sep  2 00:51 ai_news_digest_20250901_171626.md
-rw-r--r--  1 runner docker 2491499 Sep  2 00:51 ai_news_digest_20250901_171626.mp3
-rw-r--r--  1 runner docker 2491499 Sep  2 00:51 ai_news_digest_20250901_171626_enhanced.mp3
-rw-r--r--  1 runner docker     643 Sep  2 00:51 ai_news_digest_20250901_171631.json
-rw-r--r--  1 runner docker    2780 Sep  2 00:51 ai_news_digest_20250901_171631.md
-rw-r--r--  1 runner docker 3009351 Sep  2 00:51 ai_news_digest_20250901_171631.mp3
-rw-r--r--  1 runner docker 3009351 Sep  2 00:51 ai_news_digest_20250901_171631_enhanced.mp3
-rw-r--r--  1 runner docker     643 Sep  2 00:51 ai_news_digest_20250901_175357.json
-rw-r--r--  1 runner docker    3501 Sep  2 00:51 ai_news_digest_20250901_175357.md
-rw-r--r--  1 runner docker 3872436 Sep  2 00:51 ai_news_digest_20250901_175357.mp3
-rw-r--r--  1 runner docker 3872436 Sep  2 00:51 ai_news_digest_20250901_175357_enhanced.mp3
-rw-r--r--  1 runner docker     643 Sep  2 00:51 ai_news_digest_20250901_203850.json
-rw-r--r--  1 runner docker    3405 Sep  2 00:51 ai_news_digest_20250901_203850.md
-rw-r--r--  1 runner docker 4099386 Sep  2 00:51 ai_news_digest_20250901_203850.mp3
-rw-r--r--  1 runner docker     643 Sep  2 00:51 ai_news_digest_20250901_204213.json
-rw-r--r--  1 runner docker    4194 Sep  2 00:51 ai_news_digest_20250901_204213.md
-rw-r--r--  1 runner docker 4890165 Sep  2 00:51 ai_news_digest_20250901_204213.mp3
-rw-r--r--  1 runner docker    2432 Sep  2 00:51 ai_news_digest_tts_20250901_171626.txt
-rw-r--r--  1 runner docker    2801 Sep  2 00:51 ai_news_digest_tts_20250901_171631.txt
-rw-r--r--  1 runner docker    3524 Sep  2 00:51 ai_news_digest_tts_20250901_175357.txt
-rw-r--r--  1 runner docker    3429 Sep  2 00:51 ai_news_digest_tts_20250901_203850.txt
-rw-r--r--  1 runner docker    4224 Sep  2 00:51 ai_news_digest_tts_20250901_204213.txt
-rw-r--r--  1 runner docker    5450 Sep  2 00:51 claude_digest_full_20250829_222259.txt
-rw-r--r--  1 runner docker    3230 Sep  2 00:51 claude_digest_full_20250901_013235.txt
-rw-r--r--  1 runner docker    3230 Sep  2 00:51 claude_digest_full_20250901_015602.txt
-rw-r--r--  1 runner docker    2672 Sep  2 00:51 claude_digest_full_20250901_113824.txt
-rw-r--r--  1 runner docker    2631 Sep  2 00:51 claude_digest_full_20250901_115502.txt
-rw-r--r--  1 runner docker    5750 Sep  2 00:51 claude_digest_tts_20250829_222259.txt
-rw-r--r--  1 runner docker    3328 Sep  2 00:51 claude_digest_tts_20250901_013235.txt
-rw-r--r--  1 runner docker    3328 Sep  2 00:51 claude_digest_tts_20250901_015602.txt
-rw-r--r--  1 runner docker    2820 Sep  2 00:51 claude_digest_tts_20250901_113824.txt
-rw-r--r--  1 runner docker    2764 Sep  2 00:51 claude_digest_tts_20250901_115502.txt
-rw-r--r--  1 runner docker     284 Sep  2 00:51 complete_topic_digest_20250829_215551.json
-rw-r--r--  1 runner docker     410 Sep  2 00:51 complete_topic_digest_20250829_222259.json
-rw-r--r--  1 runner docker     442 Sep  2 00:51 complete_topic_digest_20250901_013235.json
-rw-r--r--  1 runner docker 4217253 Sep  2 00:51 complete_topic_digest_20250901_013235.mp3
-rw-r--r--  1 runner docker     442 Sep  2 00:51 complete_topic_digest_20250901_015602.json
-rw-r--r--  1 runner docker 4263646 Sep  2 00:51 complete_topic_digest_20250901_015602.mp3
-rw-r--r--  1 runner docker     445 Sep  2 00:51 complete_topic_digest_20250901_115502.json
-rw-r--r--  1 runner docker 3499617 Sep  2 00:51 complete_topic_digest_20250901_115502.mp3
-rw-r--r--  1 runner docker     590 Sep  2 00:51 daily_digest_20250901_013235.json
-rw-r--r--  1 runner docker    3230 Sep  2 00:51 daily_digest_20250901_013235.md
-rw-r--r--  1 runner docker 4241076 Sep  2 00:51 daily_digest_20250901_013235.mp3
-rw-r--r--  1 runner docker 4241076 Sep  2 00:51 daily_digest_20250901_013235_enhanced.mp3
-rw-r--r--  1 runner docker     590 Sep  2 00:51 daily_digest_20250901_015602.json
-rw-r--r--  1 runner docker    3230 Sep  2 00:51 daily_digest_20250901_015602.md
-rw-r--r--  1 runner docker 4222686 Sep  2 00:51 daily_digest_20250901_015602.mp3
-rw-r--r--  1 runner docker 4222686 Sep  2 00:51 daily_digest_20250901_015602_enhanced.mp3
-rw-r--r--  1 runner docker     590 Sep  2 00:51 daily_digest_20250901_113824.json
-rw-r--r--  1 runner docker    2672 Sep  2 00:51 daily_digest_20250901_113824.md
-rw-r--r--  1 runner docker 3566490 Sep  2 00:51 daily_digest_20250901_113824.mp3
-rw-r--r--  1 runner docker 3566490 Sep  2 00:51 daily_digest_20250901_113824_enhanced.mp3
-rw-r--r--  1 runner docker     590 Sep  2 00:51 daily_digest_20250901_115502.json
-rw-r--r--  1 runner docker    2631 Sep  2 00:51 daily_digest_20250901_115502.md
-rw-r--r--  1 runner docker 3486242 Sep  2 00:51 daily_digest_20250901_115502.mp3
-rw-r--r--  1 runner docker 3486242 Sep  2 00:51 daily_digest_20250901_115502_enhanced.mp3
-rw-r--r--  1 runner docker    3328 Sep  2 00:51 daily_digest_tts_20250901_013235.txt
-rw-r--r--  1 runner docker    3328 Sep  2 00:51 daily_digest_tts_20250901_015602.txt
-rw-r--r--  1 runner docker    2820 Sep  2 00:51 daily_digest_tts_20250901_113824.txt
-rw-r--r--  1 runner docker    2764 Sep  2 00:51 daily_digest_tts_20250901_115502.txt
-rw-r--r--  1 runner docker     708 Sep  2 00:55 societal_culture_change_digest_20250902_005315.json
-rw-r--r--  1 runner docker    4184 Sep  2 00:53 societal_culture_change_digest_20250902_005315.md
-rw-r--r--  1 runner docker 4901034 Sep  2 00:55 societal_culture_change_digest_20250902_005315.mp3
-rw-r--r--  1 runner docker 4901034 Sep  2 00:55 societal_culture_change_digest_20250902_005315_enhanced.mp3
-rw-r--r--  1 runner docker    4208 Sep  2 00:54 societal_culture_change_digest_tts_20250902_005315.txt
-rw-r--r--  1 runner docker     710 Sep  2 00:57 tech_news_and_tech_culture_digest_20250902_005409.json
-rw-r--r--  1 runner docker    4761 Sep  2 00:54 tech_news_and_tech_culture_digest_20250902_005409.md
-rw-r--r--  1 runner docker 5059440 Sep  2 00:56 tech_news_and_tech_culture_digest_20250902_005409.mp3
-rw-r--r--  1 runner docker 5059440 Sep  2 00:57 tech_news_and_tech_culture_digest_20250902_005409_enhanced.mp3
-rw-r--r--  1 runner docker    4792 Sep  2 00:55 tech_news_and_tech_culture_digest_tts_20250902_005409.txt
=== Topic-Specific Digest Files ===
📄 Found digest: daily_digests/ai_news_digest_20250901_203850.md
📄 Found digest: daily_digests/daily_digest_20250901_113824.md
📄 Found digest: daily_digests/daily_digest_20250901_115502.md
📄 Found digest: daily_digests/societal_culture_change_digest_20250902_005315.md
📄 Found digest: daily_digests/ai_news_digest_20250901_204213.md
📄 Found digest: daily_digests/ai_news_digest_20250901_171626.md
📄 Found digest: daily_digests/daily_digest_20250901_013235.md
📄 Found digest: daily_digests/daily_digest_20250901_015602.md
📄 Found digest: daily_digests/tech_news_and_tech_culture_digest_20250902_005409.md
📄 Found digest: daily_digests/ai_news_digest_20250901_171631.md
📄 Found digest: daily_digests/ai_news_digest_20250901_175357.md
=== All TTS Text Files ===
📝 Found TTS text: daily_digests/claude_digest_tts_20250901_015602.txt
📝 Found TTS text: daily_digests/societal_culture_change_digest_tts_20250902_005315.txt
📝 Found TTS text: daily_digests/tech_news_and_tech_culture_digest_tts_20250902_005409.txt
📝 Found TTS text: daily_digests/claude_digest_tts_20250901_115502.txt
📝 Found TTS text: daily_digests/ai_news_digest_tts_20250901_204213.txt
📝 Found TTS text: daily_digests/daily_digest_tts_20250901_015602.txt
📝 Found TTS text: daily_digests/daily_digest_tts_20250901_113824.txt
📝 Found TTS text: daily_digests/claude_digest_tts_20250829_222259.txt
📝 Found TTS text: daily_digests/daily_digest_tts_20250901_013235.txt
📝 Found TTS text: daily_digests/claude_digest_tts_20250901_113824.txt
📝 Found TTS text: daily_digests/ai_news_digest_tts_20250901_171626.txt
📝 Found TTS text: daily_digests/daily_digest_tts_20250901_115502.txt
📝 Found TTS text: daily_digests/ai_news_digest_tts_20250901_175357.txt
📝 Found TTS text: daily_digests/claude_digest_tts_20250901_013235.txt
📝 Found TTS text: daily_digests/ai_news_digest_tts_20250901_171631.txt
📝 Found TTS text: daily_digests/ai_news_digest_tts_20250901_203850.txt
=== Topic-Specific Audio Files ===
🎵 Found audio: daily_digests/ai_news_digest_20250901_203850.mp3
🎵 Found audio: daily_digests/tech_news_and_tech_culture_digest_20250902_005409_enhanced.mp3
🎵 Found audio: daily_digests/ai_news_digest_20250901_175357.mp3
🎵 Found audio: daily_digests/daily_digest_20250901_113824_enhanced.mp3
🎵 Found audio: daily_digests/daily_digest_20250901_013235_enhanced.mp3
🎵 Found audio: daily_digests/daily_digest_20250901_113824.mp3
🎵 Found audio: daily_digests/ai_news_digest_20250901_171631_enhanced.mp3
🎵 Found audio: daily_digests/societal_culture_change_digest_20250902_005315_enhanced.mp3
🎵 Found audio: daily_digests/daily_digest_20250901_013235.mp3
🎵 Found audio: daily_digests/complete_topic_digest_20250901_013235.mp3
🎵 Found audio: daily_digests/tech_news_and_tech_culture_digest_20250902_005409.mp3
🎵 Found audio: daily_digests/ai_news_digest_20250901_171626.mp3
🎵 Found audio: daily_digests/daily_digest_20250901_115502.mp3
🎵 Found audio: daily_digests/daily_digest_20250901_015602_enhanced.mp3
🎵 Found audio: daily_digests/ai_news_digest_20250901_171626_enhanced.mp3
🎵 Found audio: daily_digests/ai_news_digest_20250901_175357_enhanced.mp3
🎵 Found audio: daily_digests/societal_culture_change_digest_20250902_005315.mp3
🎵 Found audio: daily_digests/complete_topic_digest_20250901_015602.mp3
🎵 Found audio: daily_digests/complete_topic_digest_20250901_115502.mp3
🎵 Found audio: daily_digests/daily_digest_20250901_115502_enhanced.mp3
🎵 Found audio: daily_digests/ai_news_digest_20250901_171631.mp3
🎵 Found audio: daily_digests/ai_news_digest_20250901_204213.mp3
🎵 Found audio: daily_digests/daily_digest_20250901_015602.mp3
=== All JSON Metadata Files ===
📊 Found metadata: daily_digests/daily_digest_20250901_113824.json
📊 Found metadata: daily_digests/ai_news_digest_20250901_204213.json
📊 Found metadata: daily_digests/tech_news_and_tech_culture_digest_20250902_005409.json
📊 Found metadata: daily_digests/ai_news_digest_20250901_175357.json
📊 Found metadata: daily_digests/ai_news_digest_20250901_203850.json
📊 Found metadata: daily_digests/societal_culture_change_digest_20250902_005315.json
📊 Found metadata: daily_digests/complete_topic_digest_20250901_013235.json
📊 Found metadata: daily_digests/complete_topic_digest_20250829_222259.json
📊 Found metadata: daily_digests/daily_digest_20250901_115502.json
📊 Found metadata: daily_digests/complete_topic_digest_20250901_015602.json
📊 Found metadata: daily_digests/ai_news_digest_20250901_171631.json
📊 Found metadata: daily_digests/daily_digest_20250901_015602.json
📊 Found metadata: daily_digests/daily_digest_20250901_013235.json
📊 Found metadata: daily_digests/complete_topic_digest_20250901_115502.json
📊 Found metadata: daily_digests/ai_news_digest_20250901_171626.json
📊 Found metadata: daily_digests/complete_topic_digest_20250829_215551.json
=== Manual Multi-Topic TTS Generation Test ===
🧪 Testing multi-topic TTS script directly...
INFO:__main__:✅ Loaded voice config for 6 topics
INFO:__main__:🎵 Music integration enabled
INFO:__main__:✅ No unprocessed digest files found
✅ No unprocessed digest files found
=== Post-TTS Directory Check ===
-rw-r--r--  1 runner docker     643 Sep  2 00:51 ai_news_digest_20250901_171626.json
-rw-r--r--  1 runner docker    2411 Sep  2 00:51 ai_news_digest_20250901_171626.md
-rw-r--r--  1 runner docker 2491499 Sep  2 00:51 ai_news_digest_20250901_171626.mp3
-rw-r--r--  1 runner docker 2491499 Sep  2 00:51 ai_news_digest_20250901_171626_enhanced.mp3
-rw-r--r--  1 runner docker     643 Sep  2 00:51 ai_news_digest_20250901_171631.json
-rw-r--r--  1 runner docker    2780 Sep  2 00:51 ai_news_digest_20250901_171631.md
-rw-r--r--  1 runner docker 3009351 Sep  2 00:51 ai_news_digest_20250901_171631.mp3
-rw-r--r--  1 runner docker 3009351 Sep  2 00:51 ai_news_digest_20250901_171631_enhanced.mp3
-rw-r--r--  1 runner docker     643 Sep  2 00:51 ai_news_digest_20250901_175357.json
-rw-r--r--  1 runner docker    3501 Sep  2 00:51 ai_news_digest_20250901_175357.md
-rw-r--r--  1 runner docker 3872436 Sep  2 00:51 ai_news_digest_20250901_175357.mp3
-rw-r--r--  1 runner docker 3872436 Sep  2 00:51 ai_news_digest_20250901_175357_enhanced.mp3
-rw-r--r--  1 runner docker     643 Sep  2 00:51 ai_news_digest_20250901_203850.json
-rw-r--r--  1 runner docker    3405 Sep  2 00:51 ai_news_digest_20250901_203850.md
-rw-r--r--  1 runner docker 4099386 Sep  2 00:51 ai_news_digest_20250901_203850.mp3
-rw-r--r--  1 runner docker     643 Sep  2 00:51 ai_news_digest_20250901_204213.json
-rw-r--r--  1 runner docker    4194 Sep  2 00:51 ai_news_digest_20250901_204213.md
-rw-r--r--  1 runner docker 4890165 Sep  2 00:51 ai_news_digest_20250901_204213.mp3
-rw-r--r--  1 runner docker    2432 Sep  2 00:51 ai_news_digest_tts_20250901_171626.txt
-rw-r--r--  1 runner docker    2801 Sep  2 00:51 ai_news_digest_tts_20250901_171631.txt
-rw-r--r--  1 runner docker    3524 Sep  2 00:51 ai_news_digest_tts_20250901_175357.txt
-rw-r--r--  1 runner docker    3429 Sep  2 00:51 ai_news_digest_tts_20250901_203850.txt
-rw-r--r--  1 runner docker    4224 Sep  2 00:51 ai_news_digest_tts_20250901_204213.txt
-rw-r--r--  1 runner docker    5450 Sep  2 00:51 claude_digest_full_20250829_222259.txt
-rw-r--r--  1 runner docker    3230 Sep  2 00:51 claude_digest_full_20250901_013235.txt
-rw-r--r--  1 runner docker    3230 Sep  2 00:51 claude_digest_full_20250901_015602.txt
-rw-r--r--  1 runner docker    2672 Sep  2 00:51 claude_digest_full_20250901_113824.txt
-rw-r--r--  1 runner docker    2631 Sep  2 00:51 claude_digest_full_20250901_115502.txt
-rw-r--r--  1 runner docker    5750 Sep  2 00:51 claude_digest_tts_20250829_222259.txt
-rw-r--r--  1 runner docker    3328 Sep  2 00:51 claude_digest_tts_20250901_013235.txt
-rw-r--r--  1 runner docker    3328 Sep  2 00:51 claude_digest_tts_20250901_015602.txt
-rw-r--r--  1 runner docker    2820 Sep  2 00:51 claude_digest_tts_20250901_113824.txt
-rw-r--r--  1 runner docker    2764 Sep  2 00:51 claude_digest_tts_20250901_115502.txt
-rw-r--r--  1 runner docker     284 Sep  2 00:51 complete_topic_digest_20250829_215551.json
-rw-r--r--  1 runner docker     410 Sep  2 00:51 complete_topic_digest_20250829_222259.json
-rw-r--r--  1 runner docker     442 Sep  2 00:51 complete_topic_digest_20250901_013235.json
-rw-r--r--  1 runner docker 4217253 Sep  2 00:51 complete_topic_digest_20250901_013235.mp3
-rw-r--r--  1 runner docker     442 Sep  2 00:51 complete_topic_digest_20250901_015602.json
-rw-r--r--  1 runner docker 4263646 Sep  2 00:51 complete_topic_digest_20250901_015602.mp3
-rw-r--r--  1 runner docker     445 Sep  2 00:51 complete_topic_digest_20250901_115502.json
-rw-r--r--  1 runner docker 3499617 Sep  2 00:51 complete_topic_digest_20250901_115502.mp3
-rw-r--r--  1 runner docker     590 Sep  2 00:51 daily_digest_20250901_013235.json
-rw-r--r--  1 runner docker    3230 Sep  2 00:51 daily_digest_20250901_013235.md
-rw-r--r--  1 runner docker 4241076 Sep  2 00:51 daily_digest_20250901_013235.mp3
-rw-r--r--  1 runner docker 4241076 Sep  2 00:51 daily_digest_20250901_013235_enhanced.mp3
-rw-r--r--  1 runner docker     590 Sep  2 00:51 daily_digest_20250901_015602.json
-rw-r--r--  1 runner docker    3230 Sep  2 00:51 daily_digest_20250901_015602.md
-rw-r--r--  1 runner docker 4222686 Sep  2 00:51 daily_digest_20250901_015602.mp3
-rw-r--r--  1 runner docker 4222686 Sep  2 00:51 daily_digest_20250901_015602_enhanced.mp3
-rw-r--r--  1 runner docker     590 Sep  2 00:51 daily_digest_20250901_113824.json
-rw-r--r--  1 runner docker    2672 Sep  2 00:51 daily_digest_20250901_113824.md
-rw-r--r--  1 runner docker 3566490 Sep  2 00:51 daily_digest_20250901_113824.mp3
-rw-r--r--  1 runner docker 3566490 Sep  2 00:51 daily_digest_20250901_113824_enhanced.mp3
-rw-r--r--  1 runner docker     590 Sep  2 00:51 daily_digest_20250901_115502.json
-rw-r--r--  1 runner docker    2631 Sep  2 00:51 daily_digest_20250901_115502.md
-rw-r--r--  1 runner docker 3486242 Sep  2 00:51 daily_digest_20250901_115502.mp3
-rw-r--r--  1 runner docker 3486242 Sep  2 00:51 daily_digest_20250901_115502_enhanced.mp3
-rw-r--r--  1 runner docker    3328 Sep  2 00:51 daily_digest_tts_20250901_013235.txt
-rw-r--r--  1 runner docker    3328 Sep  2 00:51 daily_digest_tts_20250901_015602.txt
-rw-r--r--  1 runner docker    2820 Sep  2 00:51 daily_digest_tts_20250901_113824.txt
-rw-r--r--  1 runner docker    2764 Sep  2 00:51 daily_digest_tts_20250901_115502.txt
-rw-r--r--  1 runner docker     708 Sep  2 00:55 societal_culture_change_digest_20250902_005315.json
-rw-r--r--  1 runner docker    4184 Sep  2 00:53 societal_culture_change_digest_20250902_005315.md
-rw-r--r--  1 runner docker 4901034 Sep  2 00:55 societal_culture_change_digest_20250902_005315.mp3
-rw-r--r--  1 runner docker 4901034 Sep  2 00:55 societal_culture_change_digest_20250902_005315_enhanced.mp3
-rw-r--r--  1 runner docker    4208 Sep  2 00:54 societal_culture_change_digest_tts_20250902_005315.txt
-rw-r--r--  1 runner docker     710 Sep  2 00:57 tech_news_and_tech_culture_digest_20250902_005409.json
-rw-r--r--  1 runner docker    4761 Sep  2 00:54 tech_news_and_tech_culture_digest_20250902_005409.md
-rw-r--r--  1 runner docker 5059440 Sep  2 00:56 tech_news_and_tech_culture_digest_20250902_005409.mp3
-rw-r--r--  1 runner docker 5059440 Sep  2 00:57 tech_news_and_tech_culture_digest_20250902_005409_enhanced.mp3
-rw-r--r--  1 runner docker    4792 Sep  2 00:55 tech_news_and_tech_culture_digest_tts_20250902_005409.txt
=== TTS Script Output Analysis ===
✅ TTS full script found
✅ TTS optimized script found
=== Topic Digest Timestamp Matching ===
📄 Latest digest file: tech_news_and_tech_culture_digest_20250902_005409
🎯 Expected audio file: daily_digests/tech_news_and_tech_culture_digest_20250902_005409.mp3
✅ MATCHING AUDIO FILE FOUND!
-rw-r--r-- 1 runner docker 5059440 Sep  2 00:56 daily_digests/tech_news_and_tech_culture_digest_20250902_005409.mp3
==========================================
1s
Run echo "=== Transcript Directory Status ==="
=== Transcript Directory Status ===
total 84
drwxr-xr-x  3 runner docker  4096 Sep  2 00:54 .
drwxr-xr-x 14 runner docker  4096 Sep  2 00:57 ..
-rw-r--r--  1 runner docker    81 Sep  2 00:51 11.txt
-rw-r--r--  1 runner docker    81 Sep  2 00:51 12.txt
-rw-r--r--  1 runner docker 59919 Sep  2 00:51 76649b42.txt
-rw-r--r--  1 runner docker   447 Sep  2 00:51 YT003.txt
drwxr-xr-x  2 runner docker  4096 Sep  2 00:54 digested
=== Digested Transcripts ===
total 208
drwxr-xr-x 2 runner docker  4096 Sep  2 00:54 .
drwxr-xr-x 3 runner docker  4096 Sep  2 00:54 ..
-rw-r--r-- 1 runner docker 27613 Sep  2 00:51 100a3d3b.txt
-rw-r--r-- 1 runner docker    71 Sep  2 00:51 11.txt
-rw-r--r-- 1 runner docker    71 Sep  2 00:51 12.txt
-rw-r--r-- 1 runner docker 11352 Sep  2 00:51 1356d2cc.txt
-rw-r--r-- 1 runner docker 18471 Sep  2 00:51 37b115ce.txt
-rw-r--r-- 1 runner docker 31184 Sep  2 00:51 39716c6b.txt
-rw-r--r-- 1 runner docker 17035 Sep  2 00:51 4746906a.txt
-rw-r--r-- 1 runner docker 19891 Sep  2 00:51 4cd9eaba.txt
-rw-r--r-- 1 runner docker  8972 Sep  2 00:51 6e2a787a.txt
-rw-r--r-- 1 runner docker 14424 Sep  2 00:51 96e71ad6.txt
-rw-r--r-- 1 runner docker   558 Sep  2 00:51 YT001.txt
-rw-r--r-- 1 runner docker   541 Sep  2 00:51 YT002.txt
-rw-r--r-- 1 runner docker 12247 Sep  2 00:51 dbfbc72b.txt
-rw-r--r-- 1 runner docker 11102 Sep  2 00:51 ed9386ee.txt
=== RSS Database Status ===
archived|2
downloaded|1
=== YouTube Database Status ===
digested|10
4s
Run actions/upload-artifact@v4
Multiple search paths detected. Calculating the least common ancestor of all paths
The least common ancestor is /home/runner/work/podcast-scraper/podcast-scraper. This will be the root directory of the artifact
With the provided path, there will be 91 files uploaded
Artifact name is valid!
Root directory input is valid!
Beginning upload of artifact content to blob storage
Uploaded bytes 8388608
Uploaded bytes 16777216
Uploaded bytes 25165824
Uploaded bytes 33554432
Uploaded bytes 41943040
Uploaded bytes 50331648
Uploaded bytes 58720256
Uploaded bytes 67108864
Uploaded bytes 75497472
Uploaded bytes 83886080
Uploaded bytes 89809410
Finished uploading artifact content to blob storage!
SHA256 digest of uploaded artifact zip is bfca9c22f328eba786ec789efc4471a3bcb590579fea26270c89e6679fdbabf0
Finalizing artifact upload
Artifact podcast-digest-31.zip successfully finalized. Artifact ID 3901746116
Artifact podcast-digest-31 has been successfully uploaded! Final size is 89809410 bytes. Artifact ID is 3901746116
Artifact download URL: https://github.com/McSchnizzle/podcast-scraper/actions/runs/17390108697/artifacts/3901746116
2s
Run git config --local user.email "action@github.com"
[main 9fcfc9c] Daily podcast digest update - 2025-09-02
 21 files changed, 111 insertions(+), 7 deletions(-)
 create mode 100644 daily_digests/societal_culture_change_digest_20250902_005315.json
 create mode 100644 daily_digests/societal_culture_change_digest_20250902_005315.md
 create mode 100644 daily_digests/societal_culture_change_digest_20250902_005315.mp3
 create mode 100644 daily_digests/societal_culture_change_digest_20250902_005315_enhanced.mp3
 create mode 100644 daily_digests/societal_culture_change_digest_tts_20250902_005315.txt
 create mode 100644 daily_digests/tech_news_and_tech_culture_digest_20250902_005409.json
 create mode 100644 daily_digests/tech_news_and_tech_culture_digest_20250902_005409.md
 create mode 100644 daily_digests/tech_news_and_tech_culture_digest_20250902_005409.mp3
 create mode 100644 daily_digests/tech_news_and_tech_culture_digest_20250902_005409_enhanced.mp3
 create mode 100644 daily_digests/tech_news_and_tech_culture_digest_tts_20250902_005409.txt
 rename transcripts/{ => digested}/37b115ce.txt (100%)
 rename transcripts/{ => digested}/39716c6b.txt (100%)
 rename transcripts/{ => digested}/4746906a.txt (100%)
 rename transcripts/{ => digested}/4cd9eaba.txt (100%)
 rename transcripts/{ => digested}/6e2a787a.txt (100%)
 rename transcripts/{ => digested}/96e71ad6.txt (100%)
 rename transcripts/{ => digested}/dbfbc72b.txt (100%)
To https://github.com/McSchnizzle/podcast-scraper
 rename transcripts/{ => digested}/ed9386ee.txt (100%)
   62f7371..9fcfc9c  main -> main
✅ Committed digest updates to both databases
2s
Run softprops/action-gh-release@v1
👩‍🏭 Creating new GitHub release for tag digest-31...
⬆️ Uploading ai_news_digest_20250901_171626.md...
⬆️ Uploading ai_news_digest_20250901_171631.md...
⬆️ Uploading ai_news_digest_20250901_175357.md...
⬆️ Uploading ai_news_digest_20250901_203850.md...
⬆️ Uploading ai_news_digest_20250901_204213.md...
⬆️ Uploading daily_digest_20250901_013235.md...
⬆️ Uploading daily_digest_20250901_015602.md...
⬆️ Uploading daily_digest_20250901_113824.md...
⬆️ Uploading daily_digest_20250901_115502.md...
⬆️ Uploading societal_culture_change_digest_20250902_005315.md...
⬆️ Uploading tech_news_and_tech_culture_digest_20250902_005409.md...
⬆️ Uploading ai_news_digest_20250901_171626_enhanced.mp3...
⬆️ Uploading ai_news_digest_20250901_171626.mp3...
⬆️ Uploading ai_news_digest_20250901_171631_enhanced.mp3...
⬆️ Uploading ai_news_digest_20250901_171631.mp3...
⬆️ Uploading ai_news_digest_20250901_175357_enhanced.mp3...
⬆️ Uploading ai_news_digest_20250901_175357.mp3...
⬆️ Uploading ai_news_digest_20250901_203850.mp3...
⬆️ Uploading ai_news_digest_20250901_204213.mp3...
⬆️ Uploading complete_topic_digest_20250901_013235.mp3...
⬆️ Uploading complete_topic_digest_20250901_015602.mp3...
⬆️ Uploading complete_topic_digest_20250901_115502.mp3...
⬆️ Uploading daily_digest_20250901_013235_enhanced.mp3...
⬆️ Uploading daily_digest_20250901_013235.mp3...
⬆️ Uploading daily_digest_20250901_015602_enhanced.mp3...
⬆️ Uploading daily_digest_20250901_015602.mp3...
⬆️ Uploading daily_digest_20250901_113824_enhanced.mp3...
⬆️ Uploading daily_digest_20250901_113824.mp3...
⬆️ Uploading daily_digest_20250901_115502_enhanced.mp3...
⬆️ Uploading daily_digest_20250901_115502.mp3...
⬆️ Uploading societal_culture_change_digest_20250902_005315_enhanced.mp3...
⬆️ Uploading societal_culture_change_digest_20250902_005315.mp3...
⬆️ Uploading tech_news_and_tech_culture_digest_20250902_005409_enhanced.mp3...
⬆️ Uploading tech_news_and_tech_culture_digest_20250902_005409.mp3...
🎉 Release ready at https://github.com/McSchnizzle/podcast-scraper/releases/tag/digest-31
1s
Post job cleanup.
Cache hit occurred on the primary key Linux-pip-57d5218f0d241cadb5c122e6101f3e19941e64965e863ead5a30525509c59da5-v1, not saving cache.
0s
Post job cleanup.
0s
Post job cleanup.
/usr/bin/git version
git version 2.51.0
Temporarily overriding HOME='/home/runner/work/_temp/9efe90ae-9246-4afa-85b4-28abe312d5c5' before making global git config changes
Adding repository directory to the temporary git global config as a safe directory
/usr/bin/git config --global --add safe.directory /home/runner/work/podcast-scraper/podcast-scraper
/usr/bin/git config --local --name-only --get-regexp core\.sshCommand
/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :"
/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
http.https://github.com/.extraheader
/usr/bin/git config --local --unset-all http.https://github.com/.extraheader
/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
0s
Cleaning up orphan processes