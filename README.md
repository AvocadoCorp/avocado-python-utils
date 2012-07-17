avocado-python-utils
====================

A collection of handy utilities put together while building Avocado's web infrastructure.

build_file_index.py
-------------------

This script takes a list of input directories containing web resources (JS, CSS, images, whathaveyou),
along with some options, and outputs a versioned directory containing the files, renamed according to their
MD5 hashes, along with a JSON index file to use as a map between the original filename and the resulting
versioned filename.

When the script is run, you'll end up with an output directory containing renamed files, along a JSON blob
that looks like this:

    {
      "css-out/base_public.css": "//avocado-static.s3.amazonaws.com/css-out/base_public-vfce4345d.css",
      "js-out/avo.js": "//avocado-static.s3.amazonaws.com/js-out/avo-v7411f264.js",
      "imgs/favicon.ico": "//avocado-static.s3.amazonaws.com/imgs/favicon-v4e15b756.ico",
      "imgs/pixel.gif": "//avocado-static.s3.amazonaws.com/imgs/pixel-vdf3e567d.gif",
      ...
    }

(Note also that inside CSS and JS files, references to other resources [eg. /static/foo-bar.png] are also updated
to match the versioned filenames found in the JSON blob.)

Using this JSON blob, you can offload static resources to a static resources server (or S3 bucket) by rewriting
references on your web frontend to read paths from the JSON index.


To use:

1. During development, serve static resources from a directory, eg. "/static/", which specifies the
<code>Cache-Control: no-cache</code> HTTP header for ease of development.

2. Inside static JavaScript and CSS files, reference other resources using this prefix, like so:

        /* CSS file located at /static/some-css-file.css */
        .some-class {
          background: url(/static/some-image.png);
        }

3. Add a helper function for templates to call that translates paths relative to /static/ to a "versioned" URL:

        <script src="{{ static_url("some-js-file.js") }}"></script>

    In development, this just needs to prepend "/static/" -- but in production, it will need to read the
    JSON index like so:

        STATIC_FILE_INDEX = os.path.join(WEB_DIR, 'static-index.json')

        _file_index = {}
        def get_static_url(filename):
          if not _file_index:
            try:
              index = open(STATIC_FILE_INDEX, 'r')
              _file_index = json.load(index)
            except:
              logging.exception('Could not read static file index.')
          return _file_index.get(filename)

4. During deployment, run this script, and include static-index.json in the deployed product:

        ./build_file_index.py path/to/static path/to/static-out --indexout path/to/web/static-index.json

5. Optionally, you can feed <code>--outprefix //some-bucket.s3.amazonaws.com/</code> or whatever arbitrary
external host to the script, and <code>rsync</code> the static-out directory the script creates
to offload static resources from your primary web host. (Note that since the files themselves are renamed,
it is possible to host mutiple versions of your static resources side-by-side, to allow for partial or gradual
rollouts, rollbacks, etc. -- in which un-deployed frontends still point at an older versioned filename.)
