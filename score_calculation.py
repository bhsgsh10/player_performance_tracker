#Constants
PLAYER_POSITION_FORWARD = 'F'
PLAYER_POSITION_MIDFIELDER = 'M'
PLAYER_POSITION_DEFENDER = 'D'

# scores will be based on player positions. The algorithm for calculating the imapct score is described as follows:
# For all players the baseline score is 5 for forwards and midfielders and 6 for defenders, and the maximum score is 10.
# Final score can go below 5 but will never go beyond 10. Weights for different actions on the field will vary for
# forwards, midfielders and defenders. Eg; a tacklev and interception is more valuable for judging
# the performance of a defender than a forward. Weights for goals and assists will remain the same for
# all players because they directly influence the outcome of the game.
class Stats:
    position = ''
    num_goals_scored = 0
    num_goals_conceded = 0
    num_assists = 0
    num_penalties = 0
    num_passes = 0
    num_shots = 0
    num_shots_on_target = 0
    num_dribbles = 0
    num_key_passes = 0
    mins_played = 0 # can tell us if he was subbed
    num_tackles = 0
    num_blocks = 0
    num_interceptions = 0
    num_fouls = 0
    card_yellow = False
    card_red = False
    num_penalty_conceded = 0
    def __init__(self, player_details):
        self.position = player_details['position']
        self.num_goals_scored = player_details['goals']['total'] 
        self.num_goals_conceded = player_details['goals']['conceded']
        self.num_assists = player_details['goals']['assists']
        self.num_penalties = player_details['penalty']['success']
        self.num_passes = player_details['passes']['total']
        self.num_shots = player_details['shots']['total']
        self.num_shots_on_target = player_details['shots']['on']
        self.num_dribbles = player_details['dribbles']['success']
        self.num_key_passes = player_details['passes']['key']
        self.mins_played = player_details['minutes_played'] # can tell us if he was subbed
        self.num_tackles = player_details['tackles']['total']
        self.num_blocks = player_details['tackles']['blocks']
        self.num_interceptions = player_details['tackles']['interceptions']
        self.num_fouls = player_details['fouls']['committed']
        self.card_yellow = True if player_details['cards']['yellow'] > 0 else False
        self.card_red = True if player_details['cards']['red'] > 0 else False
        # there's a spelling error in the response, which is why here we have used 'commited' instead of 'committed'
        self.num_penalty_conceded = player_details['penalty']['commited'] 
    
    #Methods to compute impact score
    def compute_impact_score(self):

        # calculate impact score
        impact_score = 0
        # scores will be based on player positions. The algorithm for calculating the imapct score is described as follows:
        # For all players the baseline score is 5 for forwards and midfielders and 6 for defenders, and the maximum score is 10.
        # Final score can go below 5 but will never go beyond 10. Weights for different actions on the field will vary for
        # forwards, midfielders and defenders. Eg; a tacklev and interception is more valuable for judging
        # the performance of a defender than a forward. Weights for goals and assists will remain the same for
        # all players because they directly influence the outcome of the game.
        card_weight = 0
        if self.card_red == True:
            card_weight = 0.5
        elif self.card_yellow == True:
            card_weight = 0.2
        if self.position == PLAYER_POSITION_FORWARD:
            weights = self.get_weights_forward()
            impact_score = 5 + (weights['goals']*self.num_goals_scored) + (weights['assists']*self.num_assists) + (weights['shots_on']*self.num_shots_on_target) + \
                        (weights['key_passes']*self.num_key_passes) + (weights['dribbles']*self.num_dribbles) + (weights['tackles']*self.num_tackles) \
                            - (weights['penalty_conceded']*self.num_penalty_conceded) - (weights['fouls']*self.num_fouls) - card_weight
        
        elif self.position == PLAYER_POSITION_MIDFIELDER:
            weights = self.get_weights_midfielder()
            impact_score = 5 + (weights['goals']*self.num_goals_scored) + (weights['assists']*self.num_assists) + (weights['shots_on']*self.num_shots_on_target) \
                            + (weights['key_passes']*self.num_key_passes) + (weights['dribbles']*self.num_dribbles) + (weights['tackles']*self.num_tackles) \
                            - (weights['penalty_conceded']*self.num_penalty_conceded) - (weights['fouls']*self.num_fouls) - card_weight
        else:
            weights = self.get_weights_defender()
            impact_score = 6 + (weights['goals']*self.num_goals_scored) + (weights['assists']*self.num_assists) + (weights['tackles']*self.num_tackles) + \
                            (weights['interceptions']*self.num_interceptions) - (weights['penalty_conceded']*self.num_penalty_conceded) \
                                - (weights['fouls']*self.num_fouls) - card_weight
        return min(impact_score, 10)

    def get_weights_forward(self):
        '''
        Returns weights for computing impact score of forwards.
        '''
        weight_dictionary = {}
        weight_dictionary['goals'] = 1.0
        weight_dictionary['assists'] = 0.5
        weight_dictionary['shots_on'] = 0.4
        weight_dictionary['key_passes'] = 0.3
        weight_dictionary['dribbles'] = 0.2
        weight_dictionary['fouls'] = 0.1
        weight_dictionary['red'] = 0.5
        weight_dictionary['yellow'] = 0.2
        weight_dictionary['tackles'] = 0.1
        weight_dictionary['duels'] = 0.1
        weight_dictionary['interceptions'] = 0.1
        weight_dictionary['penalty_conceded'] = 0.3
        return weight_dictionary

    def get_weights_midfielder(self):
        '''
        Returns weights for computing imapct score of midfielders
        '''
        weight_dictionary = {}
        weight_dictionary['goals'] = 1.0
        weight_dictionary['assists'] = 0.5
        weight_dictionary['shots_on'] = 0.4
        weight_dictionary['key_passes'] = 0.3
        weight_dictionary['dribbles'] = 0.1
        weight_dictionary['fouls'] = 0.1
        weight_dictionary['red'] = 0.5
        weight_dictionary['yellow'] = 0.2
        weight_dictionary['tackles'] = 0.1
        weight_dictionary['duels'] = 0.1
        weight_dictionary['interceptions'] = 0.2
        weight_dictionary['penalty_conceded'] = 0.3

        return weight_dictionary

    def get_weights_defender(self):
        '''
        Returns weights for computing impact score of defenders. Less data is available for defenders.
        '''
        weight_dictionary = {}
        weight_dictionary['goals'] = 1.0
        weight_dictionary['assists'] = 0.5
        weight_dictionary['fouls'] = 0.1
        weight_dictionary['red'] = 0.5
        weight_dictionary['yellow'] = 0.2
        weight_dictionary['tackles'] = 0.3
        weight_dictionary['blocks'] = 0.2
        weight_dictionary['duels'] = 0.2
        weight_dictionary['interceptions'] = 0.5
        weight_dictionary['penalty_conceded'] = 0.3

        return weight_dictionary

