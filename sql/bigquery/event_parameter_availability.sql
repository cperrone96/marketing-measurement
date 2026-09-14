/* Public Google Analytics sample only. Grain: event name + event-parameter key.
This aggregate discovery result contains no user, session, transaction, or event identifier. */
SELECT
  event_name,
  parameter.key AS parameter_key,
  COUNT(*) AS parameter_occurrences,
  COUNTIF(parameter.value.string_value IS NOT NULL) AS string_value_occurrences,
  COUNTIF(parameter.value.int_value IS NOT NULL) AS int_value_occurrences
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`,
UNNEST(event_params) AS parameter
WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
GROUP BY event_name, parameter_key
ORDER BY event_name, parameter_occurrences DESC, parameter_key;
