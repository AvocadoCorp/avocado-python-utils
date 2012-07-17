#!/usr/bin/env python2.7

import argparse
import copy
import errno
import json
import re
import os
import subprocess

from os import path


def mkdir_p(path):
  """Utility for mimicking mkdir -p [path]."""
  try:
    os.makedirs(path)
  except OSError as e:
    if e.errno != errno.EEXIST:
      raise

def copy_file(original, destination, update_content=None):
  """
  Copies the file from `original` to `destination`, updating the content
  inside to use versioned URL references if applicable.
  """
  dirname = path.dirname(destination)
  mkdir_p(dirname)

  infile = open(original, 'r')
  try:
    incontent = infile.read()
  except:
    infile.close()

  if update_content:
    outcontent = update_content(incontent)
  else:
    outcontent = incontent

  outfile = open(destination, 'w')
  try:
    outfile.write(outcontent)
  finally:
    outfile.close()


def get_common_parent(dirlist):
  paths = {}
  for path in dirlist:
    pieces = path.split('/')
    current_base = paths
    for segment in pieces:
      if segment:
        if segment not in current_base:
          current_base[segment] = {}
        current_base = current_base[segment]

  common_parent = '/'
  current_parent = paths
  while len(current_parent) == 1:
    segment = current_parent.keys()[0]
    common_parent += '%s/' % segment
    current_parent = current_parent[segment]

  return common_parent


def _get_md5(filename):
  pieces = subprocess.check_output(['md5', filename]).split()
  return pieces[-1]

def _get_md5sum(filename):
  pieces = subprocess.check_output(['md5sum', filename]).split()
  return pieces[0]

get_md5 = _get_md5
try:
  subprocess.check_output(['which', 'md5'])
except subprocess.CalledProcessError:
  get_md5 = _get_md5sum


def find_files(dirlist):
  files = subprocess.check_output(['find'] + dirlist).split()
  for filename in files:
    if not path.isfile(filename) or path.basename(filename).startswith('.'):
      continue
    yield filename


def versioned_filename(filename, md5sum):
  parts = filename.split('.')
  suffix = '-v' + md5sum[:8]
  if len(parts) == 1:
    return filename + suffix
  else:
    return '.'.join(parts[:-1]) + suffix + '.' + parts[-1]


class VersionedFileIndex(object):
  REPLACE_CONTENT_INSIDE_RE = re.compile(r'\.(js|css)$')

  def __init__(self, parent_dir, source_prefix, output_prefix):
    self._index = {}

    # /home/avocado/src/foo/bar/static/
    self._parent_dir = parent_dir
    # "/static/" -- URLs in static resources are prefixed with this.
    self._source_prefix = source_prefix
    # "/static-out/" -- URLs in versioned resources will be prefixed with this.
    self._output_prefix = output_prefix

    self._replace_content_re = re.compile((
      r"(['\"\(])" +
        "(%s(?:[\w-]+/)*[\w-]+\.[a-z]{1,4})" +
      "(['\"\)])") % re.escape(source_prefix))

  def add_file(self, source):
    md5sum = get_md5(source)
    relative_path = source.replace(self._parent_dir, '')
    self._index[relative_path] = versioned_filename(relative_path, md5sum)

  def _update_content(self, file_content):
    def _replace_static_url(matchobj):
      start, filename, end = matchobj.groups()
      relative_filename = filename.replace(self._source_prefix, '', 1)
      if relative_filename in self._index:
        out_filename = self._index[relative_filename]
        relative_filename = path.join(self._output_prefix,
            out_filename)
      return ''.join([start, relative_filename, end])

    return self._replace_content_re.sub(_replace_static_url, file_content)

  def build_output_tree(self, output_path):
    for relative_path, versioned_path in self._index.iteritems():
      source = path.join(self._parent_dir, relative_path)
      destination = path.join(output_path, versioned_path)

      update_content = None
      if VersionedFileIndex.REPLACE_CONTENT_INSIDE_RE.search(source):
        update_content = self._update_content
      copy_file(source, destination, update_content=update_content)

  def get_index(self):
    return dict([(fin, path.join(self._output_prefix, fout))
                 for fin,fout in self._index.iteritems()])


def main():
  parser = argparse.ArgumentParser(description='Build a versioned file index.')

  parser.add_argument('sourcedirs',
      nargs='+',
      help="""
          The input directories. If one directory, the output from this
          directory goes into outdir. If multiple directories, outdir
          starts at the largest common base path of all of the input
          directories.
      """)
  parser.add_argument('outdir',
      nargs=1,
      help="""
          The directory (relative to current path) where to dump the
          versioned output tree.
      """)
  parser.add_argument('--sourceprefix',
      default=None,
      help="""
          Prefix for static files on the server, eg. "/static/". If not
          supplied, this will be the last component of the `basesourcedir`.
      """)
  parser.add_argument('--outprefix',
      default=None,
      help="""
          Prefix for versioned static files on the output server,
          eg. "/static-out/". If not supplied, this will be the last component
          of the path in `outdir`.
      """)
  parser.add_argument('--indexout',
      default=None,
      help="""
          Filename of the JSON file listing each source (foo.js) and its
          current version as it appears in the output tree (foo-v120294.js).
      """)
  parser.add_argument('--basesourcedir',
      default=None,
      help="""
          The base directory, which should correspond to --sourceprefix in the
          filesystem. If not supplied, the common parent of [sourcedirs] will
          be determined and used instead.
      """)

  args = parser.parse_args()

  source_dirs = [path.abspath(p) for p in args.sourcedirs]
  for source in source_dirs:
    if not path.isdir(source):
      print 'Not a directory:', source
      exit(1)

  # Figures out the deepest common parent dir for all the input dirs.
  parent_dir = get_common_parent(source_dirs)
  if args.basesourcedir:
    base_source_dir = path.abspath(args.basesourcedir)
    if not parent_dir.startswith(base_source_dir):
      print 'All source directories not contained within --basesourcedir.'
      exit(1)
    if not base_source_dir.endswith('/'):
      base_source_dir += '/'
    parent_dir = base_source_dir

  sourceprefix = '/%s/' % parent_dir.rstrip('/').split('/')[-1]
  if args.sourceprefix:
    sourceprefix = args.sourceprefix

  out_dir = path.abspath(args.outdir[0])
  outprefix = '/%s/' % out_dir.rstrip('/').split('/')[-1]
  if args.outprefix:
    outprefix = args.outprefix

  # Build the index dict and also copy the files to the output dir.
  index = VersionedFileIndex(parent_dir, sourceprefix, outprefix)

  for filename in find_files(source_dirs):
    index.add_file(filename)

  # Actually copies all the files, modifying some along the way, to their
  # versioned filename destinations.
  index.build_output_tree(out_dir)

  # Finally, write the file.
  jsonout = json.dumps(index.get_index())
  if args.indexout:
    indexout = open(args.indexout, 'w')
    try:
      indexout.write(jsonout)
    finally:
      indexout.close()
  else:
    print jsonout


if __name__ == '__main__':
  main()
