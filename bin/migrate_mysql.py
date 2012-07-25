#!/usr/bin/env python2.7

import argparse
import glob
import logging
import os
import os.path

try:
  import MySQLdb
except ImportError:
  print 'Could not find MySQLdb, which is required by this script.'
  exit(1)


def log(message, *args):
  print message % args
  logging.info(message, *args)


class SimpleMigrator(object):
  def __init__(self, database_host, database_name, database_user, database_password):
    self.database_host = database_host
    self.database_name = database_name
    self.database_user = database_user
    self.database_password = database_password

    self.setup()

  def setup(self):
    # Test the connection on its own. This will throw an error if it cannot
    # authenticate with the database.
    self.make_connection()

    try:
      log('Finding tables...')
      self.execute('SHOW TABLES')
    except MySQLdb.OperationalError:
      log('-- Not found! Creating database...')
      self.execute('CREATE DATABASE `%s`' % self.database_name,
          use_avocado=False)

    tables = set(self.execute('SHOW TABLES'))
    if 'migrations' not in tables:
      log('-- Creating migrations table...')
      self.execute('CREATE TABLE migrations ' +
          '(migration_name VARCHAR(255) PRIMARY KEY)')

  def make_connection(self):
    connection = MySQLdb.connect(
        self.database_host,
        self.database_user,
        self.database_password)
    connection.autocommit(True)
    return connection

  def execute(self, command, use_avocado=True):
    connection = self.make_connection()
    cursor = connection.cursor()

    try:
      if use_avocado:
        cursor.execute('USE `%s`' % self.database_name)
      cursor.execute(command)

      results = []
      for result in cursor:
        if len(result) == 1:
          result = result[0]
        results.append(result)
    finally:
      cursor.close()
      connection.close()

    return results

  def get_previous_migrations(self):
    return self.execute('SELECT * FROM migrations')

  def migrate(self, migration_name, migration_command, is_rerun=False):
    try:
      if not is_rerun:
        self.execute("INSERT INTO `migrations` (migration_name) VALUES ('%s')" % migration_name)
      self.execute(migration_command)
    except MySQLdb.Error as e:
      log('FAILED: %s -- this requires manual intervention! Be careful.',
          migration_name)
      raise


def find_migrations(migrations_dir):
  migrations_map = {}
  all_migrations = glob.glob(os.path.join(migrations_dir, '*.sql'))
  for migration_filename in all_migrations:
    migration_file = None
    try:
      migration_file = file(migration_filename, 'r')
      migration_name = os.path.basename(migration_filename.replace('.sql', ''))
      migrations_map[migration_name] = migration_file.read()
    finally:
      if migration_file:
        migration_file.close()
  return migrations_map


def migrate(migrations_dir, database_host, database_name, username, password,
    rerun_migrations=None):
  log('Beginning database migration for %s:%s', database_host,
      database_name)

  try:
    migrator = SimpleMigrator(database_host, database_name, username, password)
  except MySQLdb.Error as e:
    log('Could not initialize the migrator! %s', e)
    exit(1)

  existing_migrations = migrator.get_previous_migrations()

  rerun_migrations = rerun_migrations or []
  for migration in rerun_migrations:
    if migration in existing_migrations:
      # Pretend we didn't see this.
      existing_migrations.remove(migration)

  all_migrations = find_migrations(migrations_dir)
  new_migration_names = set(all_migrations.keys()) - set(existing_migrations)

  if not new_migration_names:
    log('-- No migrations to perform!')
  else:
    for migration_name in sorted(new_migration_names):
      log('-- Running migration: %s...', migration_name)
      rerun = migration_name in rerun_migrations
      migrator.migrate(migration_name, all_migrations[migration_name], is_rerun=rerun)


def main():
  parser = argparse.ArgumentParser(description='Migrate a database.')

  parser.add_argument('database_name',
      nargs=1,
      help='The database name to migrate.')
  parser.add_argument('--database_host',
      default='localhost',
      help='The database host, defaults to localhost.')
  parser.add_argument('--username',
      default='root',
      help='The database username, defaults to root.')
  parser.add_argument('--password',
      default='',
      help='The database password, defaults to blank.')

  parser.add_argument('--rerun',
      default=None,
      help='The migration name to attempt to re-run.')

  parser.add_argument('--migrations_dir',
      default='migrations',
      help='The directory containing migrations (named SQL files) to run.')

  args = parser.parse_args()

  migrations_dir = os.path.abspath(args.migrations_dir)
  if not os.path.isdir(migrations_dir):
    print '--migrations_dir must be a directory.'
    exit(1)

  reruns = []
  if args.rerun:
    reruns.append(args.rerun)

  # Actually perform the migration.
  migrate(migrations_dir, args.database_host, args.database_name[0],
      args.username, args.password, rerun_migrations=reruns)


if __name__ == '__main__':
  main()
