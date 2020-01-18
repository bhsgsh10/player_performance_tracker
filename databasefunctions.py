import psycopg2
from psycopg2.extras import execute_values
import os

port = int(os.environ.get("port"))
username = os.environ.get("username")
password = os.environ.get("soccerdbpassword")
endpoint = os.environ.get("soccerdbendpoint")
dbname = os.environ.get("soccerdb")


def open_database(dbname, user, password, endpoint, port):
    #connect to database
    conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=endpoint, port=port)
    return conn

#Create a cursor to perform db actions
def set_cursor(conn):
    cur = conn.cursor()
    return cur

def wipe_database(cur):
    '''
    Wipes all contents and tables from the database. Basically a reset
    '''
    cur.execute("DROP SCHEMA public CASCADE;")
    cur.execute("CREATE SCHEMA public;")
    cur.execute("GRANT ALL ON SCHEMA public TO postgres;")
    cur.execute("GRANT ALL ON SCHEMA public TO public;")

#Close database at the end
def close_database(conn, cursor):
    cursor.close()
    conn.close()
    
######################################################
# Functions for creating tables
######################################################

# The tables we need to create are player-club (player Id primary key, club Id foreign key), club-schedule (fixture Id primary key)
def create_players_table(cur, conn):
    '''
    Creates table for storing player_id, name and team_id
    '''
    try:
        cur.execute("""CREATE TABLE players (player_id varchar(64) PRIMARY KEY, player_name text, 
        team_id varchar(64) references teams(team_id), num_subscribers int, player_twitter_handle varchar(64));""")
        print('Created Players table')
    except:
        print("something went wrong creating the players table")

def create_teams_table(cur, conn):
    '''
    Creates table to store team id and name
    '''
    try:
        cur.execute("""CREATE TABLE teams (team_id varchar(64) PRIMARY KEY, team_name text, team_nickname text);""")
        print('Created teams table')
    except:
        print("failed to create teams table")

def create_team_schedule_table(cur, conn):
    '''
    Creates table to store schedules of all the teams
    '''
    try:
        cur.execute("""CREATE TABLE schedules (fixture_id varchar(64) PRIMARY KEY, league_id varchar(64),
        home_team_id varchar(64), home_team_name text, away_team_id varchar(64),
        away_team_name text, event_date text, event_timestamp numeric, status text);""")
        print('Created team schedule')
    except:
        print("something went wrong creating the schedules table")

def create_subscribers_table(cur, conn):
    '''
    Create table to store information of subscribers. Primary key is a composite of twitter handle of the subscriber and player_id.
    One subscriber can follow multiple players
    '''
    try:
        cur.execute("""CREATE TABLE subscribers (twitter_handle varchar(64), player_id varchar(64) references players,
        team_id varchar(64) references teams, original_tweet_id varchar(64), PRIMARY KEY(twitter_handle, player_id));""")
        print('Created team schedule')
    except:
        print("something wrong with the subscribers table")

def create_temp_fixtures_table(cur, conn):
    '''
    Creates table to store fixtures on a given day. Table contents should be flushed at the end of each day.
    '''
    try:
        cur.execute("""CREATE TABLE temp_fixtures (fixture_id varchar(64) PRIMARY KEY, league_id varchar(64),
        home_team_id varchar(64), home_team_name text, away_team_id varchar(64),
        away_team_name text, event_date text, event_timestamp numeric, status text);""")
        conn.commit()
    except:
        print('Failed to create temp_fixtures table')

def create_tables(cur,conn):
    '''
    creates the tables required initially.
    '''

    create_teams_table(cur, conn)
    create_players_table(cur, conn)
    create_team_schedule_table(cur, conn)
    create_subscribers_table(cur, conn)

    conn.commit()

######################################################
# Functions for storing data in tables
######################################################
def store_subscriber(cur, conn, twitter_handle, player_name, tweet_id):
    '''
    Stores subscriber's Twitter handle in the database along with the name of the player and his team_id
    Calls update_num_subscribers() to update the players table
    '''
    # First run a select query on the player table to retrieve player_id and team_id. Then form a tuple of name, id and team_id and
    #  enter in the subscriber table
    try:
        select_query = f"select player_id, team_id from players where player_name='{player_name}'"
        cur.execute(select_query)
        player = cur.fetchall()[0]
        player_id = player[0]
        team_id = player[1]
        print(f"player_id is {player_id} and team_id is {team_id}")
        execute_values(cur, """INSERT INTO subscribers (twitter_handle, player_id, team_id, original_tweet_id) VALUES %s
                        ON CONFLICT (twitter_handle, player_id) DO NOTHING""", [(twitter_handle, player_id, team_id, tweet_id)])
        conn.commit()
    except:
        print("Failed to run one or more queries")    

    update_num_subscribers(cur, conn, True, player_name)

def store_players(cur, conn, player_tuples):
    print(player_tuples)
    try:
        execute_values(cur, """INSERT INTO players (player_id, player_name, team_id, num_subscribers, player_twitter_handle) VALUES %s ON CONFLICT (player_id) DO NOTHING""", 
                    player_tuples)
        conn.commit()
    except psycopg2.OperationalError as e:
        print(e)
    
def update_num_subscribers(cur, conn, incrementValue, player_name):
    '''
    Updates num_subscribers for a given player depending on whether incrementValue is true or false. 
    If true, then num_subscribers is increased by 1 else it is decreased by 1
    '''
    print('Updating num_subscribers')
    player_id = get_player_id(cur, conn, player_name)
    update_num_subscribers_from_id(cur, conn, True, player_id)

def update_num_subscribers_from_id(cur, conn, incrementValue, player_id):
    print(f"player_id is {player_id}")
    if incrementValue == True:
        cur.execute("UPDATE players SET num_subscribers=num_subscribers+1 where player_id=%s", (player_id,))
    else:
        cur.execute("UPDATE players SET num_subscribers=num_subscribers-1 where player_id=%s and num_subscribers>1", (player_id,))
    conn.commit()
    # try:
        
    # except:
    #     print('Failed to update num_subscribers in players table')


def store_teams(cur, conn, team_tuples):
    print(team_tuples)
    try:
        execute_values(cur, """INSERT INTO teams (team_id, team_name, team_nickname) VALUES %s ON CONFLICT (team_id) DO NOTHING""", team_tuples)
        print('Added teams successfully')
        conn.commit()
    except:
        print('Failed to insert teams')

def delete_all_schedules(cur, conn):
    '''
    Deletes all fixtures from the schedules table
    '''
    try:
        cur.execute("DELETE FROM schedules")
        conn.commit()
        print('Schedules deleted')
    except:
        print('Could not delete schedule')

def store_schedules(cur, conn, schedule):
    '''
    Stores the schedule of the team sent in the argument
    '''
    fixture_list = []
    for fixture in schedule:
        fixture_tuple = (fixture['fixture_id'], fixture['league_id'], fixture['homeTeam_id'],
                        fixture['homeTeam'], fixture['awayTeam_id'], fixture['awayTeam'], fixture['event_date'],
                        int(fixture['event_timestamp']), fixture['status'])
        fixture_list.append(fixture_tuple)
    try:
        execute_values(cur, """INSERT INTO schedules (fixture_id, league_id, home_team_id, home_team_name,
                away_team_id, away_team_name, event_date, event_timestamp, status) VALUES %s 
                ON CONFLICT (fixture_id) DO NOTHING""", fixture_list)
        conn.commit()
        print('new schedule uploaded')
    except psycopg2.OperationalError as e :
        print(e)



def store_temp_fixture(cur, conn, fixture):
    '''
    Stores given fixture in the temp_fixtures table
    '''
    temp_fixture_tuple = (fixture['fixture_id'], fixture['league_id'], fixture['homeTeam_id'],
                        fixture['homeTeam'], fixture['awayTeam_id'], fixture['awayTeam'], fixture['event_date'],
                        int(fixture['event_timestamp']), fixture['status'])
    try:
        execute_values(cur, """INSERT INTO schedules (fixture_id, league_id, home_team_id, home_team_name,
                    away_team_id, away_team_name, event_date, event_timestamp, status) VALUES %s 
                    ON CONFLICT (fixture_id) DO NOTHING""", [temp_fixture_tuple])
        conn.commit()
    except:
        print('Failed to insert fixture')

######################################################
# Functions for readiing values from tables
######################################################
def get_player_list(cur, conn):
    '''
    Returns all player names that can be tracked
    '''
    select_query = "select player_name from players"
    cur.execute(select_query)
    players_tuples = cur.fetchall()
    players = []
    for player in players_tuples:
        players.append(player[0])
    return players

def get_subscriber_list(cur, conn):
    '''
    Returns details of all subscribers
    '''
    select_query = "select * from subscribers"
    cur.execute(select_query)
    subscriber_tuples = cur.fetchall()
    return subscriber_tuples

def get_schedule(cur, conn, team_id):
    '''
    Returns schedule of specified team
    '''
    select_query = f"select * from schedules where home_team_id='{team_id}' or away_team_id='{team_id}' order by event_timestamp"
    cur.execute(select_query)
    schedule = cur.fetchall()
    return schedule

def get_player_id(cur, conn, player_name):
    '''
    Returns player id for given player name.
    '''
    select_query = f"select player_id from players where player_name='{player_name}'"
    cur.execute(select_query)
    player_id = cur.fetchall()[0]
    return player_id

def get_player_name(player_id):
    '''
    Returns player_name for given player_id
    '''
    conn = open_database(dbname, username, password, endpoint, port)
    cur = set_cursor(conn)
    select_query = f"select player_name from players where player_id='{player_id}'"
    cur.execute(select_query)
    player_name = cur.fetchall()[0][0]
    close_database(conn, cur)
    return player_name

def get_team_name(cur, conn, team_id):
    '''
    Returns team name from given team_id
    '''
    select_query = f"select team_name from teams where team_id='{team_id}'"
    cur.execute(select_query)
    team_name = cur.fetchall()[0][0]
    return team_name

def check_subscription_details(cur, conn, twitter_handle):
    conn = open_database(dbname, username, password, endpoint, port)
    cur = set_cursor(conn)
    select_query = f"select player_id from subscribers where twitter_handle='{twitter_handle}'"
    cur.execute(select_query)
    player_ids = cur.fetchall()
    parsed_player_ids = []
    for player_id in player_ids:
        parsed_player_ids.append(player_id[0])
    
    close_database(conn, cur)
    return parsed_player_ids

#############################################################
# Deletions
#############################################################
def delete_subscriber(twitter_handle):
    '''
    Deletes subscriber with the given twitter handle from the database
    '''
    conn = open_database(dbname, username, password, endpoint, port)
    cur = set_cursor(conn)
    player_ids = check_subscription_details(cur, conn, twitter_handle)
    if len(player_ids) > 0:
        print(twitter_handle)
        try:
            cur.execute("DELETE FROM subscribers WHERE twitter_handle=%s", (twitter_handle,))
            #execute_values(cur, """DELETE FROM subscribers WHERE twitter_handle=%s""",(twitter_handle,))
            conn.commit()
            # decrement the num_subscribers for these in the players table
            for player_id in player_ids:
                update_num_subscribers_from_id(cur, conn, False, player_id)
            close_database(conn, cur)
        except:
            print(f"Failed to delete {twitter_handle} from the subscribers table")


if __name__ == "__main__":
    # create the tables
    #Set database connection
    conn = open_database(dbname, username, password, endpoint, port)
    cur = set_cursor(conn)
   # wipe_database(cur)
   # create_tables(cur, conn)

    # form the list of players and teams
    # teams first

    # teams = [(40, 'Liverpool', 'The Reds'),
    #  (50, 'Manchester City', 'ManCity'),
    #  (46, 'Leicester City', 'The Foxes'),
    #  (49, 'Chelsea', 'The Blues'),
    #  (39, 'Wolverhampton Wanderers', 'Wolves'),
    #  (33, 'Manchester United', 'ManUtd'),
    #  (47, 'Tottenham Hotspur', 'Spurs'),
    #  (42, 'Arsenal', 'Gunners')]
    # store_teams(cur, conn, teams)
    # #players
    # players = [(18788, 'Jamie Vardy', 46, 0, 'vardy7'),
    #             (1465, 'Pierre-Emerick Aubameyang', 42, 0, 'Aubameyang7'),
    #             (19194, 'Tammy Abraham', 49, 0, 'tammyabraham'),
    #             (909, 'Marcus Rashford', 33, 0,  'MarcusRashford'),
    #             (645, 'Raheem Sterling', 50, 0, 'sterling7'),
    #             (184, 'Harry Kane', 47, 0,  'HKane'),
    #             (642, 'Sergio Aguero', 50, 0, 'aguerosergiokun'),
    #             (306, 'Mohamed Salah', 40, 0, 'MoSalah'),
    #             (304, 'Sadio Mane', 40, 0, ''),
    #             (17, 'Christian Pulisic', 49, 0, 'cpulisic_10'),
    #             (629, 'Kevin De Bruyne', 50, 0, 'DeBruyneKev'),
    #             (283, 'Trent Alexander-Arnold', 40, 0, 'trentaa98'),
    #             (186, 'Son Heung-Min', 47, 0, 'hm_sin7'),
    #             (172, 'Dele Ali', 47, 0, ''),
    #             (290, 'Virgil van Dijk', 40, 0, 'VirgilvDijk'),
    #             (2285, 'Antonio Rudiger', 49, 0, 'ToniRuediger'),
    #             (2935, 'Harry Macguire', 33, 0, 'HarryMaguire93'),
    #             (2294, 'Willian', 49, 0, 'willianborges88'),
    #             (18784, 'James Maddison', 46, 0, 'Madders10'),
    #             (2887, 'Raùl Jimenez', 39, 0, 'Raul_Jimenez9'),
    #             (18753, 'Adama Traoré', 39, 0, 'AdamaTrd37')]
                
    # store_players(cur, conn, players)

    #create_temp_fixtures_table(cur, conn)
    close_database(conn, cur)