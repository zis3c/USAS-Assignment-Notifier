module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'header-max-length': [2, 'always', 100],
    'body-max-line-length': [0, 'always'],
    // Dependabot writes its subject as "Bump <dep> from a to b" (sentence-case),
    // which no Dependabot setting lowercases, so this rule only ever fires on
    // the bot. Type and length are still enforced.
    'subject-case': [0, 'always'],
  },
};
