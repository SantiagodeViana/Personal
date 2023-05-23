import java.util.InputMismatchException;
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {

        Scanner teclado = new Scanner(System.in);
        int prueba = -1;
        System.out.println("Por favor inserte (prueba):");
        do{
            try{
                prueba = teclado.nextInt();
            }
            catch (InputMismatchException e) { //Muestra error en caso de no recibirse números
                System.out.println("Valor incorrecto. Por favor introduce un numero.");
                teclado.nextLine(); //teclado.nextLine() limpia el valor introducido en el teclado, evitando que el mensaje se muestre indefinidamente.
            }
        }  while (prueba < 0 || prueba > 9);

        System.out.println("El número escogido es: " + prueba);

        int [][] sudoku = {{0, 0, 3, 0, 2, 0, 6, 0, 0},
                {9, 0, 0, 3, 0, 5, 0, 0, 1},
                {0, 0, 1, 8, 0, 6, 4, 0, 0},
                {0, 0, 8, 1, 0, 2, 9, 0, 0},
                {7, 0, 0, 0, 0, 0, 0, 0, 8},
                {0, 0, 6, 7, 0, 8, 2, 0, 0},
                {0, 0, 2, 6, 0, 9, 5, 0, 0},
                {8, 0, 0, 2, 0, 3, 0, 0, 9},
                {0, 0, 5, 0, 1, 0, 3, 0, 0}};

        int N = sudoku.length;
        boolean[][] visitados = new boolean [N][N];

        Sudoku.solucion(sudoku, visitados);
    }
}
