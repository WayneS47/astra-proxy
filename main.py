openapi: 3.1.0
info:
  title: Astra Weather Actions
  version: 1.0.0
  description: >
    Model-safe weather schema for Astra. All orchestration happens server-side.
    Weather data returned as opaque text payload.
servers:
  - url: https://astra-proxy.onrender.com
paths:
  /geocode:
    get:
      operationId: geocodeLocation
      summary: Convert place name to coordinates
      parameters:
        - name: city
          in: query
          required: true
          schema:
            type: string
          description: City name
        - name: state
          in: query
          required: true
          schema:
            type: string
          description: State abbreviation or name
      responses:
        '200':
          description: Coordinates resolved
          content:
            application/json:
              schema:
                type: object
                required:
                  - lat
                  - lon
                  - confidence
                properties:
                  lat:
                    type: number
                    description: Latitude in decimal degrees
                  lon:
                    type: number
                    description: Longitude in decimal degrees
                  confidence:
                    type: string
                    enum:
                      - exact
                      - approximate
                    description: Geocoding confidence level
        '400':
          description: Invalid or missing parameters
        '502':
          description: Geocoding service unavailable
  /weather-raw:
    get:
      operationId: getWeatherRaw
      summary: Retrieve raw weather data as opaque string
      parameters:
        - name: lat
          in: query
          required: true
          schema:
            type: number
          description: Latitude in decimal degrees
        - name: lon
          in: query
          required: true
          schema:
            type: number
          description: Longitude in decimal degrees
      responses:
        '200':
          description: Raw weather payload
          content:
            text/plain:
              schema:
                type: string
                description: >
                  Opaque string containing full weather payload.
                  Must not be interpreted or reformatted by the model.
        '400':
          description: Invalid or missing parameters
        '502':
          description: Weather service unavailable
