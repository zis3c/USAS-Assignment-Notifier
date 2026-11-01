module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'header-max-length': [2, 'always', 100],
    'body-max-line-length': [0, 'always'],
    // Disabled because Dependabot emits sentence-case subjects ("Bump <dep> from a to b").
    'subject-case': [0, 'always'],
  },
};
