import pandas as pd
import logging, random
from difflib import SequenceMatcher

from log.loggers.rotating_logger import get_rotating_logger

# Set up rotating logger with 10MB max size and 5 backup files
logger = get_rotating_logger(__name__)

# TODO: Swich from using Pandas to using builtin dict functionality for
#       performance boost.
# TODO: use RegEx to look for features in these strings.


def _punctuation(s: str) -> str:
    pass


def fuzzy_check(row):
    # This function accepts a row from the trivia database and determines how
    # well the question matches the Bot's policy.

    # 0 levels:
    #   0. Question is valid and no action required.

    #   1. Question is valid but minor touch ups might be needed.
    #       - Improper capitalization, punctuation, etc. (e.g. "What Is The Capital Of France.")
    #       - Possible types or spelling mistakes in question string.   (e.g. "What is the captial of Franec?")
    #       - Possible unclear language.    (e.g. Q:"French capital main city?" A:"Paris")
    #       - Possible formatting errors. (e.g. Space before or after question/answer string.)
    #       - Answer string contains stop words or unwanted punctuation. (e.g. Q: "What fruit is commonly mistaken as a vegetable?" A: "The Tomato.")
    #           > Always include stop words that are a part of a proper noun. (e.g. "The Who", "The Beatles", "The Rolling Stones", etc.)
    #       - Answer string contains words that are really long. (e.g. "Anthropomorphism") (not always an issue)
    #       - Answer string contains a mix of numbers and unit names. (e.g. "5 feet", "5ft", "5 ft", "5'") (It is best to modify the question to make the answer be just a number.)

    #   2. Question is not good and might be annoying if asked in chat. Action required.
    #       - Question or answer is too long.
    #       - Answer appears to be multiple choice format.
    #       - Question is too similar to another question.
    #       - Likely unclear language in question or answer.
    #       - Bad characters in question/answer string. (e.g. Ê or ¬¬¬)
    #       - Question contains the name of numbers instead of the number. (e.g. "One", "Seven feet", "thirty", etc.)
    #       - Possible spelling mistake in the answer string.

    #   3. Serious problems. Question should be disabled until fixed.
    #       - Any slurs, banned phrases, automod flags, etc.\
    #       - Any repeated character more than 6 times. (eg. ååååååå)

    pass


class TriviaData:
    def __init__(
        self,
        path="../blammo-bot-private/trivia.csv",
        allow_load=True,  # use False when testing or anticipating unsafe behavior
    ):
        self.path = path
        self.allow_load = allow_load

        if self.allow_load:
            self.df = pd.read_csv(path, index_col=False, header=0, encoding="latin-1")
        else:
            self.df = None

    # def _val_question(self, : str):
    #     # returns a string that is valid for the csv file
    #     if string

    def reload(self):
        if self.allow_load:
            # TODO: investigate non-UTF-8 encoding issues.
            #       Maybe add a validation function to catch and disable non-UTF-8 question?
            self.df = pd.read_csv(
                self.path, index_col=False, header=0, encoding="latin-1"
            )

    # try seeding the df.sample() function with utc time code
    def question(self):
        do_shuffle = random.choices([True, False], weights=[0.01, 0.99], k=1)[0]
        if do_shuffle:
            logger.info("Shuffling trivia questions...")
            # shuffle the dataframe
            self.df = self.df.sample(frac=1).reset_index(drop=True)
            logger.info("Done shuffling trivia questions.")

        if not self.allow_load:
            return
        # select a random row from the self.df object
        found_valid = False
        while not found_valid:
            q_df = self.df.sample(n=1)
            q = q_df.to_dict("records")[0]

            if (
                q["enabled"] == True
                or q["enabled"] == "TRUE"
                and str(q["question"]) != "nan"
                and str(q["correct_answer"]) != "nan"
            ):
                if "not" not in str(q["question"]):  # TEMPORARY FIX!
                    found_valid = True
            else:
                q_df.to_csv(
                    "../blammo-bot-private/rejected_questions.csv",
                    mode="a",
                    header=False,
                    index=False,
                    lineterminator='\n'
                )
                hbar = "=" * 81
                logger.info(f"{hbar}\nQuestion disabled, trying again...")
                logger.info(f'Question: {q["question"]}')
                logger.log(8, f'type(q["question"]): {type(q["question"])}')
                logger.info(f'Answer: {q["correct_answer"]}')
                logger.log(8, f'type(q["correct_answer"]): {type(q["correct_answer"])}')
                logger.info(f'qid: {q["qid"]}')
                logger.log(8, f'type(q["qid"]): {type(q["qid"])}')
                logger.info(f"")

        removed_char = False
        if str(q["question"])[-1] == "Ê":
            q["question"] = q["question"][:-1]
            logger.warning(f'Removed invalid character from question: {q["question"]}')
            removed_char = True
        if str(q["correct_answer"])[-1] == "Ê":
            q["correct_answer"] = q["correct_answer"][:-1]
            logger.warning(
                f'Removed invalid character from answer: {q["correct_answer"]}'
            )
            removed_char = True
        if removed_char:
            logger.info(f'Question: {q["question"]}')
            logger.info(f'Answer: {q["correct_answer"]}')

        return str(q["question"]), str(q["correct_answer"]), str(q["qid"])

    def check_duplicates(self, similarity_threshold=0.8, answer_similarity_threshold=0.85):
        """Check for duplicate and similar questions/answers using fuzzy matching.
        
        Args:
            similarity_threshold (float): Minimum similarity ratio to consider questions similar (0.0-1.0)
            answer_similarity_threshold (float): Minimum similarity ratio to consider answers similar (0.0-1.0)
        """
        if not self.allow_load or self.df is None:
            logger.warning("Cannot check duplicates: data not loaded")
            return
            
        logger.info("Starting duplicate check for trivia questions...")
        
        # Check for similar questions
        self._check_similar_questions(similarity_threshold)
        
        # Check for duplicate answers (exact matches)
        self._check_duplicate_answers()
        
        # Check for similar answers (fuzzy matches)
        self._check_similar_answers(answer_similarity_threshold)
        
        logger.info("Duplicate check completed")
    
    def _check_similar_questions(self, threshold):
        """Check for similar questions using fuzzy string matching."""
        questions = self.df['question'].dropna().astype(str).tolist()
        similar_pairs = []
        
        for i, q1 in enumerate(questions):
            for j, q2 in enumerate(questions[i+1:], i+1):
                similarity = SequenceMatcher(None, q1.lower(), q2.lower()).ratio()
                if similarity >= threshold:
                    qid1 = self.df.iloc[i]['qid'] if 'qid' in self.df.columns else f"row_{i}"
                    qid2 = self.df.iloc[j]['qid'] if 'qid' in self.df.columns else f"row_{j}"
                    similar_pairs.append({
                        'qid1': qid1,
                        'qid2': qid2,
                        'question1': q1,
                        'question2': q2,
                        'similarity': similarity
                    })
        
        if similar_pairs:
            logger.warning(f"Found {len(similar_pairs)} pairs of similar questions:")
            for pair in similar_pairs:
                logger.warning(
                    f"Similar questions (similarity: {pair['similarity']:.3f}):\n"
                    f"  QID {pair['qid1']}: {pair['question1']}\n"
                    f"  QID {pair['qid2']}: {pair['question2']}"
                )
        else:
            logger.info("No similar questions found")
    
    def _check_duplicate_answers(self):
        """Check for duplicate answers and log them separately."""
        if 'correct_answer' not in self.df.columns:
            logger.warning("No 'correct_answer' column found")
            return
            
        answers = self.df['correct_answer'].dropna().astype(str)
        answer_counts = answers.str.lower().value_counts()
        duplicates = answer_counts[answer_counts > 1]
        
        if not duplicates.empty:
            logger.warning(f"Found {len(duplicates)} duplicate answers:")
            for answer, count in duplicates.items():
                # Find all questions with this answer
                matching_rows = self.df[self.df['correct_answer'].str.lower() == answer.lower()]
                logger.warning(f"Answer '{answer}' appears {count} times:")
                for _, row in matching_rows.iterrows():
                    qid = row['qid'] if 'qid' in self.df.columns else "unknown"
                    question = row['question'] if 'question' in self.df.columns else "unknown"
                    logger.warning(f"  QID {qid}: {question}")
        else:
            logger.info("No duplicate answers found")
    
    def _check_similar_answers(self, threshold):
        """Check for similar answers using fuzzy string matching."""
        if 'correct_answer' not in self.df.columns:
            logger.warning("No 'correct_answer' column found for similar answer check")
            return
            
        answers = self.df['correct_answer'].dropna().astype(str).tolist()
        similar_pairs = []
        
        # Track which answers we've already processed to avoid duplicates
        processed_pairs = set()
        
        for i, a1 in enumerate(answers):
            for j, a2 in enumerate(answers[i+1:], i+1):
                # Skip if answers are exactly the same (handled by duplicate check)
                if a1.lower() == a2.lower():
                    continue
                    
                similarity = SequenceMatcher(None, a1.lower().strip(), a2.lower().strip()).ratio()
                if similarity >= threshold:
                    # Create a sorted pair key to avoid duplicate reporting
                    pair_key = tuple(sorted([i, j]))
                    if pair_key not in processed_pairs:
                        processed_pairs.add(pair_key)
                        
                        qid1 = self.df.iloc[i]['qid'] if 'qid' in self.df.columns else f"row_{i}"
                        qid2 = self.df.iloc[j]['qid'] if 'qid' in self.df.columns else f"row_{j}"
                        q1 = self.df.iloc[i]['question'] if 'question' in self.df.columns else "unknown"
                        q2 = self.df.iloc[j]['question'] if 'question' in self.df.columns else "unknown"
                        
                        similar_pairs.append({
                            'qid1': qid1,
                            'qid2': qid2,
                            'question1': q1,
                            'question2': q2,
                            'answer1': a1,
                            'answer2': a2,
                            'similarity': similarity
                        })
        
        if similar_pairs:
            logger.warning(f"Found {len(similar_pairs)} pairs of similar answers:")
            for pair in similar_pairs:
                logger.warning(
                    f"Similar answers (similarity: {pair['similarity']:.3f}):\n"
                    f"  QID {pair['qid1']}: Q: {pair['question1'][:60]}{'...' if len(pair['question1']) > 60 else ''} | A: {pair['answer1']}\n"
                    f"  QID {pair['qid2']}: Q: {pair['question2'][:60]}{'...' if len(pair['question2']) > 60 else ''} | A: {pair['answer2']}"
                )
        else:
            logger.info("No similar answers found")

    @classmethod
    def check_guess(guess: str, answer: str) -> bool:
        """Checks if the guess is correct.

        Args:
            guess (str): user guess to be checked
            answer (str): correct answer to be checked against

        Returns:
            bool: True if correct, False if incorrect
        """
        return
