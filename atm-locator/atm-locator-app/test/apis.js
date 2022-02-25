const { expect } = require('chai');
const got = require('got');
const { startApiBuilder, stopApiBuilder } = require('./_base');

describe('APIs', function () {
	this.timeout(30000);
	let apibuilder;
	let user;
	let client;

	/**
	 * Start API Builder and create a user.
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

		const record = {
			first_name: 'Johnny',
			last_name: 'Test',
			email: 'jtest@axway.com'
		};
		const model = apibuilder.getModel('testuser');
		return new Promise((resolve, reject) => {
			model.create(record, (err, result) => {
				if (err) {
					reject(err);
				} else {
					user = result;
					resolve();
				}
			});
		});
	});

	/**
	 * Stop API Builder after the tests.
	 */
	after(() => stopApiBuilder(apibuilder));

	describe('testapi', () => {
		it('[API-0001] should be able to hit testapi programmatically', async () => {
			const api = apibuilder.getAPI('api/testapi/:id');
			expect(api).to.not.be.undefined;
			const body = await new Promise((resolve, reject) => {
				api.execute({ id: user.getPrimaryKey() }, (err, body) => {
					if (err) {
						return reject(err);
					}
					return resolve(body);
				});
			});
			expect(body).to.have.property('success', true);
			expect(body).to.have.property('request-id');
			expect(body).to.have.property('key', 'testuser');
			expect(body).to.have.property('testuser');
			expect(body.testuser).to.have.property('id');
			expect(body.testuser).to.have.property('first_name', user.first_name);
			expect(body.testuser).to.have.property('last_name', user.last_name);
			expect(body.testuser).to.have.property('email', user.email);
		});

		it('[API-0002] should be able to hit testapi via http', async () => {
			const response = await client.get(`api/testapi/${user.getPrimaryKey()}`, {
				responseType: 'json'
			});
			expect(response.statusCode).to.equal(200);
			const body = response.body;
			expect(body).to.have.property('success', true);
			expect(body).to.have.property('request-id');
			expect(body).to.have.property('key', 'testuser');
			expect(body).to.have.property('testuser');
			expect(body.testuser).to.have.property('id');
			expect(body.testuser).to.have.property('first_name', user.first_name);
			expect(body.testuser).to.have.property('last_name', user.last_name);
			expect(body.testuser).to.have.property('email', user.email);
		});
	});
});
