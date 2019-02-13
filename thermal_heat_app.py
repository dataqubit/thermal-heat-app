"""

"Thermal Heat" monitoring app
based on Python Dash.

Dashboard for real-time monitoring of data stream from FLIR Lepton 3.0 thermal imaging sensor.
The dashboard connects to PostgreSQL on AWS and pulls the latest data.


Version 0.1
Python 3.6.7 
02/12/2019

DataQubit

"""


import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
from plotly import tools
import pandas as pd
import numpy as np
import json
import datetime as dt
from sqlalchemy import create_engine



# define colors 
colors = {
	'text': '#1C3658',
	'background': '#0a0133',
	'plotBackground': '#082149',
	'plotText': '#eeffb7',
	'headerBackground': '#506864'
}


# PostgreSQL database credentials
with open('postgresql_credentials.json', 'r') as f:
	psql = json.load(f)


### Utility Functions for PostgreSQL ####

def create_psql_engine(psql):
	""" create connection engine to PostgreSQL by providing a sqlachemy engine """
	engine = create_engine(
		'postgresql://%s:%s@%s:%s/%s' %(psql['username'], psql['password'], 
										psql['host'], psql['port'], psql['database']),
		echo=False)
	return engine

# create connection egnine
engine = create_psql_engine(psql)

def query_to_df(sql_query, con=engine):
	""" return dataframe from the sql_query """
	try:
		# if connection engine is still alive, try to generate dataframe immediately
		return pd.read_sql_query(sql_query, con=con)
	except:
		# if engine is dead, create it again
		engine = create_psql_engine(psql)
		return pd.read_sql_query(sql_query, con=engine)

def telemetry_SQL_query(timestamp_i, resample_sec=300):
	"""
	timestamp_i - initial timestamp in the table
	resample_sec - group by the time step (in seconds) (5 min by default) 
	"""
	# parameters to extract from the table
	param_names = ['total_mean', 'total_median', 'total_max', 'couch_mean',
		'couch_median', 'couch_max', 'desk_mean', 'desk_median', 'desk_max']
	# part of the SQL query
	param_wrapper = ',\n'.join(['\t AVG(%s) AS %s_avg' %(param, param) 
		for param in param_names])
	sql_query = """
	SELECT %s,
		max(timestamp) AS ts, 
		AVG(base_desk_label) AS avg_base_desk_label,
		ceil(EXTRACT(EPOCH FROM timestamp) / %f) AS epoch_resample 
	FROM nextlrlepton
	WHERE timestamp > '%s' 
	GROUP BY epoch_resample
	ORDER BY epoch_resample;
	""" %(param_wrapper, resample_sec, str(timestamp_i))

	return sql_query

def heatmap_SQL_query(timestamp_i):
	sql_query = """
	SELECT DISTINCT ON (date_trunc('minute', timestamp)) date_trunc('minute', timestamp) AS ts,
		pix_data 
	FROM nextlrlepton 
	WHERE timestamp > '%s'""" %timestamp_i

	return sql_query

### Parameters initializations ####

# set update frequency and timedelta for lookback window
telemetry_update_interval = 5 * 60 * 1000 # in miliseconds
telemetry_timedelta = pd.Timedelta('3 hours')

heatmap_update_interval = 5 * 60 * 1000 # in miliseconds
heatmap_timedelta = pd.Timedelta('1 hour')

all_telemetry_update_interval = 60 * 60 * 1000 # in miliseconds
# earliest timestamp in the database
earliest_timestamp = query_to_df("SELECT MIN(timestamp) FROM nextlrlepton;").iloc[0][0]


### Dash App ####

app = dash.Dash('Thermal Heat App')
server = app.server

app.layout  = html.Div(style={'backgroundColor': colors['background']}, children=[

	# Row 1: Header

	html.Div([

				html.Div([      
					html.H3('Thermal Heat App'),
					html.H4('Monitoring Thermal Heat data with FLIR Lepton 3.5', style={'color':  "#ede3de"}),
					], className = "nine columns padded" ),

			], className = "row",  style={'backgroundColor': colors['headerBackground'] }),

	html.Br([], style={'lineHeight': 5}),

	# Row 2: telemetry graphs row

	html.Div([


		
		html.Div([
			dcc.Graph(id='live-telemetry-graph'),
			dcc.Interval(
			id='live-telemetry-interval',
			interval=telemetry_update_interval,
			n_intervals=0)

			],
			className = "two columns", 
			style={'margin': '0 auto', 'width': 1500,'padding': '0 20'}),



		], className='row',
		   style={"margin": '0 auto', 'align': 'center', 'width': 1500}),

	html.Br([], style={'lineHeight': 3}),

	# Row 3: heatmap graphs row

	html.Div([


		
		html.Div([
			dcc.Graph(id='live-heatmap-graph'),
			dcc.Interval(
			id='live-heatmap-interval',
			interval=heatmap_update_interval,
			n_intervals=0)

			],
			className = "two columns", 
			style={'margin': '0 auto', 'width': 1500, 'padding': '0 20'}),



		], className='row',
		   style={"margin": '0 auto', 'align': 'center', 'width': 1500}),

	html.Br([], style={'lineHeight': 3}),

	# Row 4: All time telemetry graph row

	html.Div([


		
		html.Div([
			dcc.Graph(id='live-telemetry-graph-all'),
			dcc.Interval(
			id='live-telemetry-interval-all',
			interval=all_telemetry_update_interval,
			n_intervals=0)

			],
			className = "two columns", 
			style={'margin': '0 auto', 'width': 1500,'padding': '0 20'}),



		], className='row',
		   style={"margin": '0 auto', 'align': 'center', 'width': 1500}),

	html.Br([], style={'lineHeight': 3}),

])


### Call Back Functions ####

@app.callback(dash.dependencies.Output('live-telemetry-graph', 'figure'),
			  [dash.dependencies.Input('live-telemetry-interval', 'n_intervals')])
def update_live_telemetry_graph(n):



	timestamp_lookback = pd.to_datetime(dt.datetime.now()) - telemetry_timedelta
	df_telemetry_lookback = query_to_df(telemetry_SQL_query(timestamp_lookback)).set_index('ts')

	# Create the graph with subplots
	telemetry_fig = tools.make_subplots(rows=2, cols=1, vertical_spacing=0.2, 
		subplot_titles=('Telemetry Data for the last 3 hours', 'Desk Occupancy Data for the last 3 hours'))
	
	trace1 = go.Scatter(
				y = df_telemetry_lookback.total_mean_avg,
				x = df_telemetry_lookback.index,
				line=dict(width=5),
				mode='lines',
				opacity=0.8,
				name='Total Temperature'
		)

	trace2 = go.Scatter(
				y = df_telemetry_lookback.couch_max_avg,
				x = df_telemetry_lookback.index,
				mode='lines',
				opacity=1.0,
				name='Couch Area Max Temperature'
		)

	trace3 = go.Scatter(
				y = df_telemetry_lookback.avg_base_desk_label,
				x = df_telemetry_lookback.index,
				mode='lines',
				line=dict(shape='vh'),
				opacity=1.0,
				name='Desk Occupancy'
		)

	telemetry_fig.append_trace(trace1, 1, 1)
	telemetry_fig.append_trace(trace2, 1, 1)
	telemetry_fig.append_trace(trace3, 2, 1)

	telemetry_fig['layout'].update(
	xaxis2={'title': 'Datetime'},
	yaxis1={'title': 'Temperature, C'},
	yaxis2={'title': 'Desk Occupancy'},
	showlegend = True,
	width = 1500, 
	height = 500,
	autosize = False,
	font=dict(color=colors['plotText']),
	titlefont=dict(color=colors['plotText'], size=12),
	plot_bgcolor=colors['plotBackground'],
	paper_bgcolor=colors['plotBackground'],
		)

	return telemetry_fig


@app.callback(dash.dependencies.Output('live-heatmap-graph', 'figure'),
			  [dash.dependencies.Input('live-heatmap-interval', 'n_intervals')])
def update_live_heatmap_graph(n):

	timestamp_lookback = pd.to_datetime(dt.datetime.now()) - heatmap_timedelta
	df_heatmap_lookback = query_to_df(heatmap_SQL_query(timestamp_lookback)).set_index('ts')

	# stack of all matrices over the lookback window
	heatmap_tensor = np.vstack(df_heatmap_lookback.pix_data)
	
	trace1 = go.Heatmap(z=heatmap_tensor.mean(axis=0).reshape(120, 160),
								 showscale=False)

	trace2 = go.Heatmap(z=heatmap_tensor.std(axis=0).reshape(120, 160),
								 showscale=False)

	heatmap_fig = tools.make_subplots(rows=1, cols=2, horizontal_spacing=0.2,
		subplot_titles=('Average Heatmap within last 1 hour', 'Standard deviation per pixel within last 1 hour'))

	heatmap_fig.append_trace(trace1, 1, 1)
	heatmap_fig.append_trace(trace2, 1, 2)

	heatmap_fig['layout'].update(
	xaxis1=dict(showticklabels=False, showgrid=False, scaleanchor="y1", scaleratio=1),
	xaxis2=dict(showticklabels=False, showgrid=False, scaleanchor="y2", scaleratio=1),
	yaxis1=dict(autorange='reversed', showgrid=False, showticklabels=False),
	yaxis2=dict(autorange='reversed', showgrid=False, showticklabels=False),
	showlegend = False,
	width = 1500,
	height=800,
	autosize = False,
	font=dict(color=colors['plotText']),
	titlefont=dict(color=colors['plotText'], size=12),
	plot_bgcolor=colors['plotBackground'],
	paper_bgcolor=colors['plotBackground'],
		)

	return heatmap_fig


@app.callback(dash.dependencies.Output('live-telemetry-graph-all', 'figure'),
			  [dash.dependencies.Input('live-telemetry-interval-all', 'n_intervals')])
def update_live_telemetry_graph_all(n):

	df_telemetry_all = query_to_df(telemetry_SQL_query(earliest_timestamp, resample_sec=15 * 60)).set_index('ts')

	# Create the graph with subplots
	
	trace1 = go.Scatter(
				y = df_telemetry_all.total_mean_avg,
				x = df_telemetry_all.index,
				line=dict(width=5),
				mode='lines',
				opacity=0.8,
				name='Total Temperature'
		)

	trace2 = go.Scatter(
				y = df_telemetry_all.couch_max_avg,
				x = df_telemetry_all.index,
				mode='lines',
				opacity=1.0,
				name='Couch Area Max Temperature'
		)

	trace3 = go.Scatter(
				y = df_telemetry_all.avg_base_desk_label,
				x = df_telemetry_all.index,
				mode='lines',
				line=dict(shape='vh'),
				opacity=1.0,
				name='Desk Occupancy'
		)

	telemetry_fig = tools.make_subplots(rows=2, cols=1, vertical_spacing=0.2,
		subplot_titles=('Telemetry Data of all time', 'Desk Occupancy Data of all time'))

	telemetry_fig.append_trace(trace1, 1, 1)
	telemetry_fig.append_trace(trace2, 1, 1)
	telemetry_fig.append_trace(trace3, 2, 1)

	telemetry_fig['layout'].update(
	xaxis2={'title': 'Datetime'},
	yaxis1={'title': 'Temperature, C'},
	yaxis2={'title': 'Desk Occupancy'},
	showlegend = True,
	width = 1500, 
	height = 500,
	autosize = False,
	font=dict(color=colors['plotText']),
	titlefont=dict(color=colors['plotText'], size=12),
	plot_bgcolor=colors['plotBackground'],
	paper_bgcolor=colors['plotBackground'],
		)

	return telemetry_fig


### Loading External CSS  ###  

external_css = [ "https://cdnjs.cloudflare.com/ajax/libs/normalize/7.0.0/normalize.min.css",
		"https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.min.css",
		"//fonts.googleapis.com/css?family=Raleway:400,300,600",
		"https://codepen.io/plotly/pen/KmyPZr.css",
		"https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css"]

for css in external_css: 
	app.css.append_css({ "external_url": css })

### Start the server ####
	
if __name__ == '__main__':
	app.run_server(debug=True, port=8050)

