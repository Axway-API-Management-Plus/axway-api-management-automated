const { expect } = require('chai');
const got = require('got');
const { startApiBuilder, stopApiBuilder } = require('./_base');

describe('Endpoints', function () {
	this.timeout(30000);
	let apibuilder;
	let client;

	/**
	 * Start API Builder.
	 */
	before(async () => {
		apibuilder = await startApiBuilder();
		const apikey = apibuilder.config.apikey;
		client = got.extend({
			prefixUrl: 'http://localhost:8080',
			headers: {
				apikey,
				authorization: `Basic ${Buffer.from(apikey + ':').toString('base64')}`
			},
			throwHttpErrors: false
		});
	});

	/**
	 * Stop API Builder after the tests.
	 */
	after(() => stopApiBuilder(apibuilder));

	describe('Greet', () => {
		it('[Endpoint-0001] should be able to hit Greet endpoint', async () => {
			const username = 'Johnny Test';
			const response = await client.get(`api/greet?username=${username}`, {
				responseType: 'json'
			});
			expect(response.statusCode).to.equal(200);
			expect(response.body).to.equal(`Howdy ${username}`);
		});

		it('[Endpoint-0002] should be able to get error response from Greet endpoint', async () => {
			const response = await client.get('api/greet', {
				responseType: 'json'
			});
			expect(response.statusCode).to.equal(400);
			expect(response.body).to.deep.equal({
				error: 'Request validation failed: Parameter (username) is required'
			});
		});
	});
});
