# player_performance_tracker
**[@PlayerTracker2](https://twitter.com/PlayerTracker2)** is a Twitter bot to allow users to track the performance and conversation around their favorite soccer players. While there are many apps and websites that have performance data on soccer players, a Twitter bot is less intrusive and can be tailored to send updates for only the updates a user has subscribed for. It can also be viewed as a reporting aid as it sends out updates on statistics of players after each game.

The main features of the bot are listed below:   
•	Notify users if a player is picked when the lineups are announced.   
•	Show stats of that player in the current season, last 5 games to give an idea of their current form   
•	Analysis of fans’ reaction to his performances in the current season (top 10 tweets based on no. of likes, comments and retweets).   
•	Impact score of the player at the end of the game.    

For this project, the bot can track a specific group of players whose names are given below:
1.	Jamie Vardy (Leicester City) 
2.	Pierre-Emerick Aubameyang (Arsenal)
3.	Tammy Abraham (Chelsea) 
4.	Marcus Rashford (Man Utd)
5.	Raheem Sterling (Man City)
6.	Harry Kane (Tottenham Hotspur)
7.	Sergio Aguero (Man City) 
8.	Mohamed Salah (Liverpool) 
9.	Sadio Mane (Liverpool) 
10.	Christian Pulisic (Chelsea) 
11.	Kevin De Bruyne (Man City) 
12.	Trent Alexander-Arnold (Liverpool)
13.	Son Heung-Min (Tottenham) 
14.	Dele Ali (Tottenham) 
15.	Virgil van Dijk (Liverpool) 
16.	Antonio Rudiger (Chelsea) 
17.	Harry Maguire (Man Utd) 
18.	Willian (Chelsea) 
19.	James Maddison (Leicester) 
20.	Raùl Jimenez (Wolverhampton Wanderers) 
21.	Adama Traore (Wolverhampton Wanderers).  
All the players in the list above play in the English Premier League. It is a mix of forwards, midfielders and defenders, though prominent goal scorers have been given preference because they tend to be in the media spotlight. The list can be modified to include more players representing different teams and leagues. Goalkeepers have not been included as the metrics to evaluate other players do not apply to goalkeepers and we would need a different methodology to rate them.

The project was built using Tweepy(Python), PostgreSQL and [API-Football](https://www.api-football.com/).

Go to https://twitter.com/PlayerTracker2 to view the list of players you can get updates for. To track a player tweet the following: '@PlayerTracker2 track <player name>'. To stop getting updates tweet '@PlayerTracker2 stop'.
  
All games are suspended at the time due to the Coronavirus pandemic. The bot will be up again when action resumes.

