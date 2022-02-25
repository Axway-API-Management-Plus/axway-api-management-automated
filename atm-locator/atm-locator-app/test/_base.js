const APIBuilder = require('@axway/api-builder-runtime');
process.env.LOG_LEVEL = process.env.LOG_LEVEL || 'FATAL';

/**
 * Start the API Builder server.
 * @return {Object} The details for the started server.
 * @property {APIBuilder} apibuilder - The API Builder server.
 * @property {Promise} started - The promise that resolves when the server is started.
 */
async function startApiBuilder() {
	const apibuilder = new APIBuilder({
		bindProcessHandlers: false
	});
	apibuilder.started = apibuilder.start();
	await apibuilder.started;
	return apibuilder;
}

/**
 * Stop the API Builder server.
 * @param {Object} apibuilder The object returned from startApiBuilder().
 * @return {Promise} The promise that resolves when the server is stopped.
 */
function stopApiBuilder(apibuilder) {
	return new Promise((resolve, reject) => {
		if (!apibuilder || !apibuilder.started) {
			return resolve();
		}
		apibuilder.started
			.then(() => {
				apibuilder.stop(() => {
					APIBuilder.resetGlobal();
					resolve();
				});
			})
			.catch(err => {
				reject(err);
			});
	});
}

exports = module.exports = {
	startApiBuilder,
	stopApiBuilder
};
