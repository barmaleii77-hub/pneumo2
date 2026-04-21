# Как поправить

1. Левое дерево должно быть главным путём входа в рабочие пространства и окна.
2. Main workflow surfaces открываются в центральной области, а не как россыпь внешних окон.
3. Advanced surfaces открываются напрямую из дерева, но ниже по иерархии и с понятной ролью.
4. Каждое окно должно иметь:
   - first-screen contract;
   - primary action;
   - immediate feedback;
   - explicit return target;
   - context preservation contract.
5. Для всех переходов нужно держать selection-sync:
   дерево → центр → inspector → status strip.
6. Для всех возвращений нужно держать state continuity:
   не сбрасывать проект, выбранный объект, dirty-state и последние связные артефакты.
