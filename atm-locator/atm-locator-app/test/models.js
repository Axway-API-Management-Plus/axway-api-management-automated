const { expect } = require('chai');
const { promisify } = require('util');
const { startApiBuilder, stopApiBuilder } = require('./_base');

describe('Models', function () {
	this.timeout(30000);
	let apibuilder;

	/**
	 * Start API Builder.
	 */
	before(async () => {
		apibuilder = await startApiBuilder();
	});

	/**
	 * Stop API Builder after the tests.
	 */
	after(() => stopApiBuilder(apibuilder));

	describe('testuser', () => {
		it('[Model-0001] verify model definition', () => {
			const model = apibuilder.getModel('testuser');
			expect(model.fields).to.deep.equal({
				first_name: {
					type: 'string',
					required: false,
					optional: true
				},
				last_name: {
					type: 'string',
					required: false,
					optional: true
				},
				email: {
					type: 'string',
					required: false,
					optional: true
				}
			});
			expect(model.connector.name).to.equal('memory');
		});

		it('[Model-0002] test CRUD methods on model', async () => {
			const model = apibuilder.getModel('testuser');

			// Use promisify for cleaner tests
			const createAsync = promisify(model.create.bind(model));
			const findByIDAsync = promisify(model.findByID.bind(model));
			const updateAsync = promisify(model.update.bind(model));
			const deleteAsync = promisify(model.delete.bind(model));

			const user = {
				first_name: 'Test',
				last_name: 'User1',
				email: 'testuser1@example.com'
			};

			// Create user, find the user, update the user, delete the user.
			const created = await createAsync(user);

			// Verify the created model
			expect(created).to.have.property('id');
			expect(created).to.have.property('first_name', user.first_name);
			expect(created).to.have.property('last_name', user.last_name);
			expect(created).to.have.property('email', user.email);

			// Find the testuser by id
			const found = await findByIDAsync(created.id);

			// Verify the found model
			expect(found).to.have.property('id', created.id);
			expect(found).to.have.property('first_name', user.first_name);
			expect(found).to.have.property('last_name', user.last_name);
			expect(found).to.have.property('email', user.email);

			// Update the testuser record.
			const update = JSON.parse(JSON.stringify(found));
			update.first_name = 'Another';
			const updated = await updateAsync(update);

			// Verify the updated model
			expect(updated).to.have.property('id', created.id);
			expect(updated).to.have.property('first_name', 'Another');
			expect(updated).to.have.property('last_name', user.last_name);
			expect(updated).to.have.property('email', user.email);

			// Delete the test user record.
			const deleted = await deleteAsync(updated.id);

			// Verify the deleted model cannot be found
			const foundDeleted = await findByIDAsync(deleted.id);
			expect(foundDeleted).to.be.undefined;
		});
	});
});
