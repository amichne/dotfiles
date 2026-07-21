Type safety is king, the compiler is our only true ally. We leverage verifiability wherever possible. A compiler error is just a bug we didn't have to have a test for, and one we can't get around, don't cast/override/circumvent them.

Above all, we are bad engineers, and we write code to protect us from ourselves. We know all engineers are bad engineers, because they all make mistakes, and thus we ought never to let ourselves be deceived into thinking intention all of a sudden implies outcomes. We test everything, verify our base cases before we move a muscle, and check anything we depend upon eagerly. All information is encoded in the type system, we avoid primitives like they will sneak up and kill us at night; because they will.

Commit and push each validated RED and passing GREEN checkpoint before continuing.

When a task, ticket, subtask, or direct message defines a deliverable or links a file containing the deliverable, raise or update a pull request and follow its latest head until green.
