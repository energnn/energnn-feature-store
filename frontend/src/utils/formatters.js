// Message parsing and personalization
export function parseApiErrorForDelete(err) {

  if (!err) return "Unknown error.";

  if (!err.response) {
    if (err.message && err.message.toLowerCase().includes("network")) {
      return "Unable to reach the server (network error). Please check that the API is running.";
    }
    return `Network error or unreachable server: ${err.message || String(err)}`;
  }

  const status = err.response.status;
  const data = err.response.data;

  // extract message
  let serverMsg = "";
  try {
    if (!data) serverMsg = "";
    else if (typeof data === "string") serverMsg = data;
    else if (data.message) serverMsg = data.message;
    else if (data.detail) serverMsg = data.detail;
    else serverMsg = JSON.stringify(data);
  } catch (e) {
    serverMsg = String(data);
  }

  console.log(serverMsg)

  // message personnalisation for each status
  switch (status) {
    case 400:
      return "Error 400: No record found for these parameters.";
    case 404:
      return "Error 404: Resource not found.";
    case 409:
      return "Error 409: Deletion impossible due to a constraint conflict.";
    case 422:
      return "Error 422: Unprocessable request.";
    case 500:
      return "Internal server error (code 500).";
    default:
      return `Unexpected error (code ${status}).`;
  }
}

/**
 * Convert an item to a string value usable in selects etc.
 * If item is a string -> returns it, otherwise attempts to read common fields.
 */
export function itemToValue(item) {
  if (item == null) return item;
  if (typeof item === "string") return item;
  return item.value ?? item.name ?? item.project_name ?? item.id ?? JSON.stringify(item);
}