avocado-python-utils
====================

A collection of handy utilities put together while building Avocado's web infrastructure.

build_file_index.py
-------------------

This script takes a list of input directories containing web resources (JS, CSS, images, whathaveyou),
along with some options, and outputs a versioned directory containing the files, renamed according to their
MD5 hashes, along with a JSON index file to use as a map between the original filename and the resulting
versioned filename.

Using this script, you can:

1. Serve versioned resource URLs and cache them infinitely.

2. Offload static resources to a static resources server (or S3 bucket) by rewriting
references on your web frontend to read paths from the JSON index.

This script was heavily inspired by VFL, the mechanism YouTube employs to serve its static resources, which
is available on <a href="http://code.google.com/p/msolo/source/browse/trunk/vfl/">Google Code</a>.

### Example output

When the script is run, you'll end up with an output directory containing renamed files, along with a JSON blob.

#### Static directories, input and output

<img src="https://github.com/AvocadoCorp/avocado-python-utils/raw/master/docs/build_static.png" alt="Versioned tree">

#### JSON index from raw to versioned name

    {
      "css-out/base_public.css": "//avocado-static.s3.amazonaws.com/css-out/base_public-vfce4345d.css",
      "js-out/avo.js": "//avocado-static.s3.amazonaws.com/js-out/avo-v7411f264.js",
      "imgs/favicon.ico": "//avocado-static.s3.amazonaws.com/imgs/favicon-v4e15b756.ico",
      "imgs/pixel.gif": "//avocado-static.s3.amazonaws.com/imgs/pixel-vdf3e567d.gif",
      ...
    }

NOTE: inside CSS and JS files, references to other resources [eg. <code>/static/foo-bar.png</code>] are
also updated to match the versioned filenames found in the JSON blob.

Also, in this case, <code>//avocado-static.s3.amazonaws.com/</code> is the <code>--outprefix</code> option.

### How to

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

migrate_mysql.py
----------------

This script simply takes a directory of named <code>.sql</code> files and runs them against the database
specified by the command-line arguments, and records what has been done in a table in the database itself.

This is very similar to migrations in Rails, but without any Ruby -- just a dead simple way to allow different
developers to make database changes while working together in a distributed environment.

If multiple new migrations are detected in the migrations directory, they are performed in order.

    ./migrate_mysql.py my_database_name    \
        --migrations_dir ./migrations/     \
        --user notroot                     \
        --password p4ssw0rd

The script in this case will search <code>./migrations/</code> for files ending in <code>.sql</code>, remove the
file extension (considering what remains the migration's unique identifier), and sort the migration identifiers,
and attempt to execute them in order.

If a migration fails due to an SQL error, you may need to manually intervene (eg. by deleting a half-created table).
The migrator, however, will consider the migration to be "run", and will not attempt to re-run it. If you'd like to
re-run a migration, you can pass the following option:

    # note that the migration name does not end in .sql
    ./migrate_mysql.py [options] --rerun 20120412_migration_name

... or just delete the migration with that name in the migrations table.