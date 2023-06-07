import streamlit as st
from statsbombpy import sb
import pandas as pd
from mplsoccer.pitch import Pitch, VerticalPitch

comp = sb.competitions()

with st.sidebar:
	league = st.selectbox("League", comp.competition_name.unique())
	season = st.selectbox("Season", comp[comp['competition_name'] == league]['season_name'])
	selected = comp[(comp['competition_name'] == league) & (comp['season_name'] == season)].reset_index()
	mat = sb.matches(competition_id = selected['competition_id'][0], season_id = selected['season_id'][0])
	mat['match'] = [mat['home_team'][i] + ' vs ' + mat['away_team'][i] + ' (' + str(mat['home_score'][i]) + ':' + str(mat['away_score'][i]) + ') (' + mat['match_date'][i] + ')' for i in range(len(mat))]
	match = st.selectbox("Match", mat.match)
	home_min = st.slider("Minimum Passes(Home)", max_value = 10)
	away_min = st.slider("Minimum Passes(Away)", max_value = 10)
	but = st.button('Plot!')

match_id = mat['match_id'][list(mat['match']).index(match)]
home_team = mat['home_team'][list(mat['match']).index(match)]
away_team = mat['away_team'][list(mat['match']).index(match)]
st.write(match_id, home_team, away_team)

def pass_network(MATCH_ID, TEAM):
	line_ups = pd.DataFrame(sb.lineups(match_id = MATCH_ID)[TEAM]).filter(['player_name', 'jersey_number'])
	events = pd.DataFrame(sb.events(match_id = MATCH_ID))
	events = events.filter(['id', 'player', 'team', 'type', 'location', 'pass_end_location', 'pass_outcome', 'pass_recipient', 'minute'])
	subs = events[events['type']=='Substitution'][events['team']==TEAM]
	if not subs.empty:
		first_sub = subs['minute'].min()
	else:
		first_sub = None
	passes = events[(events['type']=='Pass') & (events['team']==TEAM)]
	passes['pass_outcome'] = passes['pass_outcome'].fillna('Successful')
	if first_sub:
		passes = passes[passes['minute']<first_sub]
	passes['x'] = [i[0] for i in passes['location']]
	passes['y'] = [i[1] for i in passes['location']]
	passes['end_x'] = [i[0] for i in passes['pass_end_location']]
	passes['end_y'] = [i[1] for i in passes['pass_end_location']]
	passes = passes.drop(['team', 'type', 'location', 'pass_end_location'], axis = 1)
	successful = passes[passes['pass_outcome']=='Successful'].reset_index()
	successful = successful.drop('index', axis=1)
	average_locations = successful.groupby('player').agg({'x':['mean'], 'y':['mean', 'count']})
	average_locations.columns = ['x', 'y', 'count']
	average_locations_new = average_locations.merge(line_ups, left_index=True, right_on='player_name').reset_index().drop('index', axis=1)
	pass_between = successful.groupby(['player', 'pass_recipient']).id.count().reset_index()
	pass_between = pass_between.rename({'id':'pass_count'}, axis = 'columns')

	pass_between = pass_between.merge(average_locations, left_on = 'player', right_index=True)
	pass_between = pass_between.merge(average_locations, left_on = 'pass_recipient', right_index=True, suffixes=['', '_end']).reset_index().drop(['index'], axis=1)

	for i in range(len(pass_between.index)):
	    if pass_between[pass_between['player']==pass_between.pass_recipient[i]][pass_between['pass_recipient']==pass_between.player[i]].empty:
	        pass_between.loc[len(pass_between.index)] = [pass_between['pass_recipient'][i], pass_between['player'][i], 0, pass_between['x_end'][i], pass_between['y_end'][i], pass_between['count_end'][i], pass_between['x'][i], pass_between['y'][i], pass_between['count'][i]]

	pass_between = pass_between.drop(['count', 'count_end'], axis=1)
	pass_between = pass_between.merge(pass_between, left_on=['player', 'pass_recipient'], right_on = ['pass_recipient','player'], suffixes=['_1', '_2'])
	i = 0
	while True:
	    ind = pass_between[pass_between['player_1']==pass_between['pass_recipient_1'][i]][pass_between['pass_recipient_1']==pass_between['player_1'][i]].index[0]
	    pass_between = pass_between.drop(ind, axis = 0).reset_index().drop('index', axis = 1)
	    if i == pass_between.index[-1]:
	        break
	    i += 1
	    
	pass_between = pass_between.drop(['x_end_1', 'y_end_1', 'pass_recipient_1', 'pass_recipient_2', 'x_end_2', 'y_end_2'], axis = 1)
	pass_between['total_pass_between'] = pass_between['pass_count_1']+pass_between['pass_count_2']

	column_names = ['player_1', 'player_2', 'total_pass_between', 'x_1', 'y_1', 'x_2', 'y_2', 'pass_count_1', 'pass_count_2']
	pass_between = pass_between.reindex(columns=column_names)
	return pass_between, average_locations_new

def plot(pass_between_h, average_locations_h, min_pass_h, pass_between_a, average_locations_a, min_pass_a):
	MAX_WIDTH = 10
	pass_between_h['width'] = (pass_between_h.total_pass_between / pass_between_h.total_pass_between.max() * MAX_WIDTH)
	pass_between_min_h = pass_between_h[pass_between_h['total_pass_between']>=min_pass_h]

	pass_between_a['width'] = (pass_between_a.total_pass_between / pass_between_a.total_pass_between.max() * MAX_WIDTH)
	pass_between_min_a = pass_between_a[pass_between_a['total_pass_between']>=min_pass_a]

	pitch = VerticalPitch(pitch_type='statsbomb', pitch_color = '#000000', line_color='#626363')
	fig, ax = pitch.draw(figsize=(18, 12), ncols = 2)

	arrows_h = pitch.lines(pass_between_min_h.x_1, pass_between_min_h.y_1, pass_between_min_h.x_2, pass_between_min_h.y_2, ax=ax[0], color='white', zorder=1, linewidth=pass_between_min_h.width, alpha=0.9)

	nodes_h = pitch.scatter(average_locations_h.x, average_locations_h.y, s=900, color='#000000', edgecolors='red', ax=ax[0])
	for i in range(11):
	  	pitch.annotate(average_locations_h.jersey_number[i], xy = (average_locations_h.x[i], average_locations_h.y[i]), va = 'center', ha='center', c='#ffffff', size=16, weight='bold', ax=ax[0])
	
	arrows_a = pitch.lines(pass_between_min_a.x_1, pass_between_min_a.y_1, pass_between_min_a.x_2, pass_between_min_a.y_2, ax=ax[1], color='white', zorder=1, linewidth=pass_between_min_a.width, alpha=0.9)

	nodes_a = pitch.scatter(average_locations_a.x, average_locations_a.y, s=900, color='#000000', edgecolors='blue', ax=ax[1])
	for i in range(11):
	  	pitch.annotate(average_locations_a.jersey_number[i], xy = (average_locations_a.x[i], average_locations_a.y[i]), va = 'center', ha='center', c='#ffffff', size=16, weight='bold', ax=ax[1])

	return fig
if but:
	home = pass_network(match_id, home_team)
	away = pass_network(match_id, away_team)
	st.pyplot(plot(home[0], home[1], home_min, away[0], away[1], away_min))

